"""Live table-occupancy worker.

Reads each enabled camera (RTSP stream or uploaded recording), detects people with YOLO,
maps them into the table zones drawn by the owner, runs the per-camera hysteresis tracker,
fuses all cameras of an outlet (any camera sees a person => occupied) and reports changes
to the API. Output is unvalidated until checked against real footage.
"""
import logging
import os
import threading
import time

import cv2
import httpx
from ultralytics import YOLO

from app.ai_operations.dishes import DISH_CLASSES, DishTracker
from app.ai_operations.fusion import FloorFusion, phases_to_occupied
from app.ai_operations.occupancy import OccupancyTracker, PersonPoint

API_URL = os.environ.get("API_URL", "http://api:8000").rstrip("/")
API_KEY = os.environ["VISION_API_KEY"]
FPS = float(os.environ.get("VISION_FPS", "1"))
CONF = float(os.environ.get("VISION_CONFIDENCE", "0.35"))
POLL_SECONDS = 30
HEARTBEAT_SECONDS = 30
# Seated people are partly hidden behind tables, so use a point 70% down the person box
# instead of the feet.
POINT_DEPTH = 0.7

log = logging.getLogger("vision")
model = YOLO(os.environ.get("VISION_MODEL", "yolov8n.pt"))
model_lock = threading.Lock()
http = httpx.Client(base_url=API_URL, headers={"X-Vision-API-Key": API_KEY}, timeout=10)
fusions: dict[int, FloorFusion] = {}
fusion_lock = threading.Lock()


dishes_by_camera: dict[int, dict[int, bool]] = {}


def detect(frame) -> tuple[list[PersonPoint], list[tuple[float, float]]]:
    """One pass finds both people and dishes/food."""
    with model_lock:
        result = model.predict(frame, classes=[0, *DISH_CLASSES], conf=CONF, verbose=False, imgsz=640)[0]
    people, dishes = [], []
    for (x1, y1, x2, y2), conf, cls in zip(result.boxes.xyxyn.tolist(), result.boxes.conf.tolist(), result.boxes.cls.tolist()):
        if int(cls) == 0:
            people.append(PersonPoint((x1 + x2) / 2, y1 + POINT_DEPTH * (y2 - y1), float(conf)))
        else:
            dishes.append(((x1 + x2) / 2, (y1 + y2) / 2))
    return people, dishes


def post(path: str, tenant_id: int, body: dict) -> None:
    try:
        http.post(path, json=body, headers={"X-Tenant-ID": str(tenant_id)}).raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("API call %s failed: %s", path, exc)


def publish(cfg: dict, fusion: FloorFusion, cameras: list[int]) -> None:
    for table_id, state in fusion.changes():
        kind = "TABLE_UNKNOWN" if state is None else ("TABLE_OCCUPIED" if state else "TABLE_FREE")
        log.info("outlet %s table %s -> %s", cfg["restaurant_id"], table_id, kind)
        post("/api/v1/internal/observations", cfg["tenant_id"], {
            "camera_id": cfg["camera_id"], "restaurant_id": cfg["restaurant_id"], "table_id": table_id,
            "observation_type": kind,
            "evidence": {"source": "yolo-person", "cameras": cameras,
                         "dishes": any(d.get(table_id) for d in dishes_by_camera.values())},
        })


def run_camera(cfg: dict, stop: threading.Event) -> None:
    zones = {r["table_id"]: (r["name"], [tuple(p) for p in r["polygon"]]) for r in cfg["regions"]}
    tracker = OccupancyTracker(zones)
    dish_tracker = DishTracker({t: poly for t, (_, poly) in zones.items()})
    outlet = cfg["restaurant_id"]
    with fusion_lock:
        fusion = fusions.setdefault(outlet, FloorFusion())
    is_file = cfg["source_type"] != "rtsp"
    last_beat = 0.0
    while not stop.is_set():
        cap = cv2.VideoCapture(cfg["source"])
        if not cap.isOpened():
            log.warning("camera %s cannot be opened; retrying", cfg["camera_id"])
            with fusion_lock:
                fusion.set_camera(cfg["camera_id"], None)
                publish(cfg, fusion, [cfg["camera_id"]])
            tracker.reset_after_outage()
            stop.wait(15)
            continue
        step = 1.0 / FPS
        video_fps = cap.get(cv2.CAP_PROP_FPS) or 25
        video_time, next_at = 0.0, time.monotonic()
        while not stop.is_set():
            if is_file:
                cap.set(cv2.CAP_PROP_POS_MSEC, video_time * 1000)
            ok, frame = cap.read()
            if not ok:
                break
            if not is_file and time.monotonic() < next_at:
                continue  # keep draining the live buffer so detections stay current
            now = video_time if is_file else time.monotonic()
            people, dish_points = detect(frame)
            tracker.update(people, now)
            dish_tracker.update(dish_points)
            dishes_by_camera[cfg["camera_id"]] = {t: dish_tracker.present(t) for t in zones}
            with fusion_lock:
                fusion.set_camera(cfg["camera_id"], phases_to_occupied({t: s.phase for t, s in tracker.states.items()}))
                publish(cfg, fusion, [cfg["camera_id"]])
            if time.monotonic() - last_beat > HEARTBEAT_SECONDS:
                last_beat = time.monotonic()
                post("/api/v1/internal/vision/heartbeat", cfg["tenant_id"], {"camera_id": cfg["camera_id"]})
            video_time += step
            next_at = time.monotonic() + step
            if is_file:
                stop.wait(step)
        cap.release()
        if not stop.is_set():
            log.info("camera %s stream ended; reconnecting", cfg["camera_id"])
            tracker.reset_after_outage()
            with fusion_lock:
                fusion.set_camera(cfg["camera_id"], None if not is_file else {})
                publish(cfg, fusion, [cfg["camera_id"]])
            stop.wait(5)
    with fusion_lock:
        fusion.remove_camera(cfg["camera_id"])
    dishes_by_camera.pop(cfg["camera_id"], None)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    running: dict[int, tuple[dict, threading.Thread, threading.Event]] = {}
    while True:
        try:
            wanted = {c["camera_id"]: c for c in http.get("/api/v1/internal/vision/cameras").raise_for_status().json()["cameras"]}
        except httpx.HTTPError as exc:
            log.warning("Could not load cameras: %s", exc)
            time.sleep(10)
            continue
        for camera_id, (cfg, thread, stop) in list(running.items()):
            if camera_id not in wanted or wanted[camera_id] != cfg or not thread.is_alive():
                stop.set()
                thread.join(timeout=20)
                del running[camera_id]
        for camera_id, cfg in wanted.items():
            if camera_id not in running:
                stop = threading.Event()
                thread = threading.Thread(target=run_camera, args=(cfg, stop), daemon=True, name=f"cam-{camera_id}")
                thread.start()
                running[camera_id] = (cfg, thread, stop)
                log.info("started camera %s (outlet %s, %d zones)", camera_id, cfg["restaurant_id"], len(cfg["regions"]))
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()

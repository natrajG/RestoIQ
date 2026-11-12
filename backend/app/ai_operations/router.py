import secrets
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.responses import FileResponse
import ipaddress
import socket
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, current_principal, require_outlet_access, require_roles
from app.core.config import settings
from app.core.audit import audit
from app.core.events import add_business_event
from app.core.realtime import redis_client
from app.auth.service import decode_access_token
from app.core.security import decrypt_camera_url, encrypt_camera_url
from app.db import SessionLocal, get_db, set_tenant_context
from app.models import Camera, DiningTable, Tenant, Floor, Observation, OperationalEvent, Restaurant, StaffTask, User, now_utc
from app.ai_operations.schemas import (
    CameraInput, CameraRegionsUpdateInput, CameraUpdateInput, StaffTaskAssignmentInput, StaffTaskCompletionInput,
    CameraObservationInput,
)
from app.ai_operations.repository import (
    active_festival_name,
    camera_by_id,
    cameras_for_outlet,
    recent_menu_demand,
    table_by_id,
    task_by_id,
    tasks_for_outlet,
)
from app.ai_operations.service import camera_regions_payload, create_staff_task, canonical_staff_role, menu_recommendations, task_to_dict

router = APIRouter(prefix="/api/v1", tags=["ai-operations"])
MANAGERS = ("owner", "manager", "admin")


@router.get("/outlets/{outlet_id}/analytics/recommendations")
def recommendations(
    outlet_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(current_principal),
):
    outlet = require_outlet_access(db, principal, outlet_id)
    recommendations_payload: list[dict] = []
    dirty = db.scalar(select(func.count(DiningTable.id)).where(
        DiningTable.tenant_id == principal.tenant_id, DiningTable.restaurant_id == outlet_id,
        DiningTable.status == "DIRTY",
    )) or 0
    pending_cleaning = db.scalar(select(func.count(StaffTask.id)).where(
        StaffTask.tenant_id == principal.tenant_id, StaffTask.restaurant_id == outlet_id,
        StaffTask.task_type == "clean_table", StaffTask.status.in_(["pending", "acknowledged"]),
    )) or 0
    if dirty or pending_cleaning:
        recommendations_payload.append({
            "title": "Review tables awaiting cleaning",
            "evidence": {"dirty_tables": dirty, "open_cleaning_tasks": pending_cleaning},
            "estimated_impact": None, "confidence": 0.85, "method": "rule",
            "measurement": "Compare departure-to-ready times after staff records cleaning completion.",
            "note": "Potential impact is not estimated without validated waiting and turnover measurements.",
        })

    now_local = datetime.now(ZoneInfo(outlet.timezone))
    active_festival = active_festival_name(
        db,
        principal.tenant_id,
        outlet_id,
        now_local.date(),
        outlet.state_code,
    )
    demand_points = recent_menu_demand(db, principal.tenant_id, outlet_id)
    recommendations_payload.extend(
        menu_recommendations(
            demand_points,
            outlet.timezone,
            now_utc_dt=now_utc(),
            active_festival=active_festival,
        )
    )

    if recommendations_payload:
        return recommendations_payload
    return [{
        "title": "Collect more operating data",
        "evidence": {"validated_camera_observations": 0},
        "estimated_impact": None, "confidence": 1.0, "method": "rule",
        "measurement": "Record service and table state timestamps before estimating opportunity.",
        "note": "No unsupported revenue claim is generated.",
    }]


def _require_floor(db: Session, principal: Principal, outlet_id: int, floor_id: int | None) -> None:
    if floor_id is not None and not db.scalar(select(Floor.id).where(
        Floor.id == floor_id, Floor.restaurant_id == outlet_id, Floor.tenant_id == principal.tenant_id,
    )):
        raise HTTPException(422, "Floor does not belong to this outlet")


def _require_tables_on_floor(db: Session, principal: Principal, outlet_id: int, floor_id: int | None, regions) -> None:
    for region in regions:
        table = table_by_id(db, principal.tenant_id, outlet_id, region.table_id)
        if not table:
            raise HTTPException(422, f"Table {region.table_id} does not belong to this outlet")
        if floor_id is not None and table.floor_id != floor_id:
            raise HTTPException(422, f"Table {table.name} is not on this camera's floor")


@router.patch("/outlets/{outlet_id}/cameras/{camera_id}")
def update_camera(
    outlet_id: int,
    camera_id: int,
    body: CameraUpdateInput,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*MANAGERS)),
):
    require_outlet_access(db, principal, outlet_id)
    camera = camera_by_id(db, principal.tenant_id, outlet_id, camera_id)
    if not camera:
        raise HTTPException(404, "Camera not found")
    if body.name is not None:
        camera.name = body.name
    if "floor_id" in body.model_fields_set:
        _require_floor(db, principal, outlet_id, body.floor_id)
        if body.floor_id is not None:
            wrong = [r["name"] for r in camera.regions if (t := table_by_id(db, principal.tenant_id, outlet_id, r["table_id"])) and t.floor_id != body.floor_id]
            if wrong:
                raise HTTPException(409, f"Remove zones for {', '.join(wrong)} before moving this camera to another floor")
        camera.floor_id = body.floor_id
    return {"id": camera.id, "name": camera.name, "floor_id": camera.floor_id}


@router.get("/outlets/{outlet_id}/camera-coverage")
def camera_coverage(
    outlet_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(current_principal),
):
    require_outlet_access(db, principal, outlet_id)
    cameras = cameras_for_outlet(db, principal.tenant_id, outlet_id)
    floors = list(db.scalars(select(Floor).where(Floor.restaurant_id == outlet_id, Floor.tenant_id == principal.tenant_id).order_by(Floor.id)))
    tables = list(db.scalars(select(DiningTable).where(DiningTable.restaurant_id == outlet_id, DiningTable.tenant_id == principal.tenant_id).order_by(DiningTable.name)))
    seen_by: dict[int, list[str]] = {}
    for cam in cameras:
        for region in cam.regions:
            seen_by.setdefault(region["table_id"], []).append(cam.name)
    result = []
    for floor in floors:
        floor_tables = [t for t in tables if t.floor_id == floor.id]
        result.append({
            "floor_id": floor.id, "floor_name": floor.name,
            "cameras": [{"id": c.id, "name": c.name, "zones": len(c.regions)} for c in cameras if c.floor_id == floor.id],
            "tables": [{"id": t.id, "name": t.name, "cameras": seen_by.get(t.id, [])} for t in floor_tables],
            "uncovered": [t.name for t in floor_tables if t.id not in seen_by],
        })
    return {"floors": result, "unassigned_cameras": [{"id": c.id, "name": c.name} for c in cameras if c.floor_id is None]}


@router.get("/outlets/{outlet_id}/cameras")
def list_cameras(
    outlet_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(current_principal),
):
    require_outlet_access(db, principal, outlet_id)
    rows = cameras_for_outlet(db, principal.tenant_id, outlet_id)
    return [{
        "id": camera.id, "name": camera.name, "source_type": camera.source_type,
        "regions": camera.regions, "enabled": camera.enabled,
        "has_reference_image": bool(camera.reference_image_path), "floor_id": camera.floor_id,
        "last_seen_at": camera.last_seen_at, "validation_status": "unvalidated",
    } for camera in rows]


INTERNAL_HOSTS = {"api", "db", "redis", "vision", "web", "worker", "beat", "localhost", "metadata.google.internal"}
INTERNAL_PORTS = {80, 443, 5432, 6379, 8000, 8080}  # RTSP is 554/8554; these ports belong to our own services


def _reject_internal_target(url: str) -> None:
    """Stop a tenant from pointing the vision worker at our own services or the cloud metadata address."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    try:
        port = parsed.port
    except ValueError as exc:
        raise HTTPException(422, "Invalid camera URL") from exc
    if not host or host in INTERNAL_HOSTS or (port in INTERNAL_PORTS):
        raise HTTPException(422, "That camera address is not allowed")
    try:
        addresses = {ipaddress.ip_address(info[4][0]) for info in socket.getaddrinfo(host, port or 554, proto=socket.IPPROTO_TCP)}
    except (socket.gaierror, ValueError):
        return  # an unresolved name is not reachable from here either; the worker will report no signal
    if any(a.is_loopback or a.is_link_local or a.is_unspecified or a.is_multicast for a in addresses):
        raise HTTPException(422, "That camera address is not allowed")


@router.post("/outlets/{outlet_id}/cameras", status_code=201)
def create_camera(
    outlet_id: int,
    body: CameraInput,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*MANAGERS)),
):
    require_outlet_access(db, principal, outlet_id)
    if body.restaurant_id != outlet_id:
        raise HTTPException(422, "Outlet ID mismatch")
    if body.source_type == "rtsp" and (not body.stream_url or not body.stream_url.startswith(("rtsp://", "rtsps://"))):
        raise HTTPException(422, "RTSP sources require an rtsp:// or rtsps:// URL")
    if body.source_type == "rtsp":
        _reject_internal_target(body.stream_url)
    try:
        regions = camera_regions_payload(body.regions)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    _require_floor(db, principal, outlet_id, body.floor_id)
    _require_tables_on_floor(db, principal, outlet_id, body.floor_id, body.regions)
    camera = Camera(
        tenant_id=principal.tenant_id, restaurant_id=outlet_id, name=body.name, floor_id=body.floor_id,
        source_type=body.source_type,
        stream_url_ciphertext=encrypt_camera_url(body.stream_url) if body.stream_url else None,
        regions=regions,
    )
    db.add(camera)
    db.flush()
    audit(db, principal, "camera_configured", "camera", camera.id, {"source_type": body.source_type})
    return {"id": camera.id, "name": camera.name, "source_type": camera.source_type, "validation_status": "unvalidated"}


@router.patch("/outlets/{outlet_id}/cameras/{camera_id}/regions")
def update_camera_regions(
    outlet_id: int,
    camera_id: int,
    body: CameraRegionsUpdateInput,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*MANAGERS)),
):
    require_outlet_access(db, principal, outlet_id)
    camera = camera_by_id(db, principal.tenant_id, outlet_id, camera_id)
    if not camera:
        raise HTTPException(404, "Camera not found")
    try:
        regions = camera_regions_payload(body.regions)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    _require_tables_on_floor(db, principal, outlet_id, camera.floor_id, body.regions)
    camera.regions = regions
    audit(db, principal, "camera_regions_updated", "camera", camera.id, {"region_count": len(regions)})
    return {"camera_id": camera.id, "regions": camera.regions}


@router.post("/outlets/{outlet_id}/cameras/{camera_id}/reference-image", status_code=201)
async def upload_reference_image(
    outlet_id: int,
    camera_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*MANAGERS)),
):
    require_outlet_access(db, principal, outlet_id)
    camera = camera_by_id(db, principal.tenant_id, outlet_id, camera_id)
    if not camera:
        raise HTTPException(404, "Camera not found")
    data = await file.read(8 * 1024 * 1024 + 1)
    await file.close()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(413, "Image exceeds 8 MB")
    if data[:3] == b"\xff\xd8\xff":
        suffix = ".jpg"
    elif data[:8] == b"\x89PNG\r\n\x1a\n":
        suffix = ".png"
    else:
        raise HTTPException(415, "Upload a JPG or PNG screenshot of the camera view")
    root = Path(settings.upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"ref-{principal.tenant_id}-{camera.id}-{uuid.uuid4().hex}{suffix}"
    path.write_bytes(data)
    if camera.reference_image_path:
        Path(camera.reference_image_path).unlink(missing_ok=True)
    camera.reference_image_path = str(path)
    audit(db, principal, "camera_reference_image_uploaded", "camera", camera.id, {"size_bytes": len(data)})
    return {"camera_id": camera.id, "has_reference_image": True}


@router.get("/outlets/{outlet_id}/cameras/{camera_id}/reference-image")
def get_reference_image(
    outlet_id: int,
    camera_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(current_principal),
):
    require_outlet_access(db, principal, outlet_id)
    camera = camera_by_id(db, principal.tenant_id, outlet_id, camera_id)
    if not camera or not camera.reference_image_path or not Path(camera.reference_image_path).is_file():
        raise HTTPException(404, "No reference image")
    return FileResponse(camera.reference_image_path, headers={"Cache-Control": "private, max-age=60"})


@router.delete("/outlets/{outlet_id}/cameras/{camera_id}", status_code=204)
def delete_camera(
    outlet_id: int,
    camera_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*MANAGERS)),
):
    require_outlet_access(db, principal, outlet_id)
    camera = camera_by_id(db, principal.tenant_id, outlet_id, camera_id)
    if not camera:
        raise HTTPException(404, "Camera not found")
    audit(db, principal, "camera_deleted", "camera", camera.id, {})
    for stored in (camera.reference_image_path, camera.recording_path):
        if stored:
            Path(stored).unlink(missing_ok=True)
    db.delete(camera)


@router.post("/outlets/{outlet_id}/cameras/{camera_id}/recording", status_code=201)
async def upload_recording(
    outlet_id: int,
    camera_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*MANAGERS)),
):
    require_outlet_access(db, principal, outlet_id)
    camera = camera_by_id(db, principal.tenant_id, outlet_id, camera_id)
    if not camera:
        raise HTTPException(404, "Camera not found")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".mp4", ".mov", ".avi", ".mkv"}:
        raise HTTPException(415, "Supported recordings: mp4, mov, avi, mkv")
    root = Path(settings.upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{principal.tenant_id}-{camera.id}-{uuid.uuid4().hex}{suffix}"
    total = 0
    try:
        with path.open("wb") as target:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > 500 * 1024 * 1024:
                    raise HTTPException(413, "Recording exceeds 500 MB")
                target.write(chunk)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    camera.recording_path = str(path)
    camera.source_type = "recording"
    audit(db, principal, "camera_recording_uploaded", "camera", camera.id, {"size_bytes": total})
    return {"camera_id": camera.id, "recording": path.name, "size_bytes": total, "validation_status": "unvalidated"}


@router.get("/outlets/{outlet_id}/staff-tasks")
def list_staff_tasks(
    outlet_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(current_principal),
):
    require_outlet_access(db, principal, outlet_id)
    rows = tasks_for_outlet(db, principal.tenant_id, outlet_id)
    if principal.role not in {"owner", "admin", "platform_admin", "manager"}:
        role = canonical_staff_role(principal.role)
        rows = [task for task in rows if task.target_role == role]
    return [task_to_dict(task) for task in rows]


def editable_task(db: Session, principal: Principal, outlet_id: int, task_id: int) -> StaffTask:
    require_outlet_access(db, principal, outlet_id)
    task = task_by_id(db, principal.tenant_id, outlet_id, task_id)
    if not task:
        raise HTTPException(404, "Staff task not found")
    role = canonical_staff_role(principal.role)
    if principal.role not in {"owner", "admin", "platform_admin", "manager"} and role != task.target_role:
        raise HTTPException(403, "Task is assigned to another staff role")
    if task.status in {"completed", "cancelled"}:
        raise HTTPException(409, "Task is already closed")
    return task


@router.post("/outlets/{outlet_id}/staff-tasks/{task_id}/assign")
def assign_staff_task(
    outlet_id: int,
    task_id: int,
    body: StaffTaskAssignmentInput,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*MANAGERS)),
):
    task = editable_task(db, principal, outlet_id, task_id)
    from app.models import Employee

    employee = db.scalar(select(Employee).where(
        Employee.id == body.employee_id, Employee.restaurant_id == outlet_id,
        Employee.tenant_id == principal.tenant_id, Employee.active.is_(True),
    ))
    if not employee:
        raise HTTPException(404, "Employee not found")
    if canonical_staff_role(employee.role) not in {task.target_role, "manager"}:
        raise HTTPException(422, f"Task is for {task.target_role} staff")
    task.assigned_employee_id = employee.id
    audit(db, principal, "staff_task_assigned", "staff_task", task.id, {"employee_id": employee.id})
    return task_to_dict(task)


@router.post("/outlets/{outlet_id}/staff-tasks/{task_id}/acknowledge")
def acknowledge_staff_task(
    outlet_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(current_principal),
):
    task = editable_task(db, principal, outlet_id, task_id)
    task.status = "acknowledged"
    task.acknowledged_at = now_utc()
    audit(db, principal, "staff_task_acknowledged", "staff_task", task.id)
    return task_to_dict(task)


@router.post("/outlets/{outlet_id}/staff-tasks/{task_id}/complete")
def complete_staff_task(
    outlet_id: int,
    task_id: int,
    body: StaffTaskCompletionInput,
    db: Session = Depends(get_db),
    principal: Principal = Depends(current_principal),
):
    task = editable_task(db, principal, outlet_id, task_id)
    task.status = "completed"
    task.completed_at = now_utc()
    if body.note:
        task.details = {**task.details, "completion_note": body.note}
    if task.task_type == "clean_table" and task.table_id:
        table = db.get(DiningTable, task.table_id)
        if table and table.tenant_id == principal.tenant_id and table.status == "DIRTY":
            table.status = "READY"
            db.add(add_business_event(
                db, principal.tenant_id, outlet_id, "TABLE_CLEANING_COMPLETED", "staff",
                table_id=table.id, payload={"task_id": task.id},
                idempotency_key=f"task:{task.id}:completed",
            ))
    if task.task_type == "serve_order" and task.order_id:
        from app.models import RestaurantOrder

        order = db.scalar(select(RestaurantOrder).where(
            RestaurantOrder.id == task.order_id, RestaurantOrder.tenant_id == principal.tenant_id,
        ))
        if order and order.status == "ready":
            order.status = "served"
            db.add(add_business_event(
                db, principal.tenant_id, outlet_id, "FOOD_DELIVERED", "staff",
                order_id=order.id, table_id=order.table_id,
                payload={"task_id": task.id}, idempotency_key=f"task:{task.id}:served",
            ))
    audit(db, principal, "staff_task_completed", "staff_task", task.id)
    db.add(add_business_event(
        db, principal.tenant_id, outlet_id, "STAFF_TASK_UPDATED", "operations",
        table_id=task.table_id, order_id=task.order_id,
        payload={"task_id": task.id, "status": task.status},
        idempotency_key=f"task:{task.id}:updated",
    ))
    return task_to_dict(task)


def _tasks_from_occupancy(db: Session, tenant_id: int, body: CameraObservationInput, previous: str | None) -> None:
    """Camera-driven staff work; needs no POS. Advisory because observations are unvalidated."""
    if body.table_id is None or body.observation_type not in ("TABLE_OCCUPIED", "TABLE_FREE"):
        return
    table = db.scalar(select(DiningTable).where(
        DiningTable.id == body.table_id, DiningTable.tenant_id == tenant_id,
        DiningTable.restaurant_id == body.restaurant_id))
    if not table:
        return
    actor = Principal(0, tenant_id, "vision", "integration")
    task_type, role, title = (
        ("greet_guests", "waiter", f"Guests seated at {table.name}: greet and take the order")
        if body.observation_type == "TABLE_OCCUPIED"
        else ("clean_table", "cleaning", f"Guests left {table.name}: "
              + ("clear the dishes and reset the table" if body.evidence.get("dishes") is True else "clean and reset the table"))
    )
    if body.observation_type == "TABLE_OCCUPIED":
        if previous == "TABLE_FREE" and table.status in ("FREE", "READY"):
            table.status = "OCCUPIED"
        elif previous != "TABLE_FREE":
            return  # first sighting after start-up or an outage is not a new party
    else:
        if previous != "TABLE_OCCUPIED":
            return
        if table.status in ("OCCUPIED", "BILLING"):
            table.status = "DIRTY"
    open_task = db.scalar(select(StaffTask.id).where(
        StaffTask.tenant_id == tenant_id, StaffTask.table_id == table.id,
        StaffTask.task_type == task_type, StaffTask.status.in_(("pending", "acknowledged"))))
    if not open_task:
        create_staff_task(db, actor, body.restaurant_id, task_type, role, title, table_id=table.id,
                          details={"source": "camera", "validation_status": "unvalidated",
                                   "dishes_on_table": body.evidence.get("dishes") is True})


@router.post("/internal/observations", status_code=202)
def ingest_camera_observation(
    body: CameraObservationInput,
    request: Request,
    tenant_id: int = Header(..., alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
):
    _require_vision_key(request)
    from app.models import Restaurant

    set_tenant_context(db, tenant_id)
    camera = db.scalar(select(Camera).where(
        Camera.id == body.camera_id, Camera.tenant_id == tenant_id,
        Camera.restaurant_id == body.restaurant_id,
    ))
    outlet = db.scalar(select(Restaurant).where(
        Restaurant.id == body.restaurant_id, Restaurant.tenant_id == tenant_id,
    ))
    if not camera or not outlet:
        raise HTTPException(404, "Camera or outlet not found")
    previous_type = db.scalar(select(Observation.observation_type).where(
        Observation.tenant_id == tenant_id, Observation.table_id == body.table_id,
        Observation.observation_type.in_(("TABLE_OCCUPIED", "TABLE_FREE", "TABLE_UNKNOWN")),
    ).order_by(Observation.id.desc()).limit(1)) if body.table_id is not None else None
    observation = Observation(
        tenant_id=tenant_id, restaurant_id=body.restaurant_id, camera_id=camera.id,
        table_id=body.table_id, observation_type=body.observation_type,
        confidence=body.confidence, validation_status="unvalidated", evidence=body.evidence,
    )
    db.add(observation)
    db.flush()
    db.add(add_business_event(
        db, tenant_id, body.restaurant_id, "CAMERA_OBSERVATION", "camera",
        table_id=body.table_id,
        payload={"observation_id": observation.id, "observation_type": body.observation_type,
                 "confidence": str(body.confidence) if body.confidence is not None else None},
        idempotency_key=f"camera-observation:{observation.id}",
        evidence_source="camera", evidence_status="unvalidated",
    ))
    camera.last_seen_at = now_utc()
    _tasks_from_occupancy(db, tenant_id, body, previous_type)
    return {"observation_id": observation.id, "validation_status": observation.validation_status}


def _require_vision_key(request: Request) -> None:
    if not secrets.compare_digest(request.headers.get("x-vision-api-key", ""), settings.vision_api_key):
        raise HTTPException(401, "Invalid vision service key")


@router.get("/internal/vision/cameras")
def vision_cameras(request: Request, db: Session = Depends(get_db)):
    """Enabled cameras with their zones and sources, for the detection worker only."""
    _require_vision_key(request)
    result = []
    for tenant_id in list(db.scalars(select(Tenant.id))):
        set_tenant_context(db, tenant_id)
        for camera in db.scalars(select(Camera).where(Camera.tenant_id == tenant_id, Camera.enabled.is_(True))):
            if not camera.regions:
                continue
            if camera.source_type == "rtsp" and camera.stream_url_ciphertext:
                source = decrypt_camera_url(camera.stream_url_ciphertext)
            elif camera.recording_path:
                source = camera.recording_path
            else:
                continue
            result.append({
                "tenant_id": tenant_id, "restaurant_id": camera.restaurant_id, "camera_id": camera.id,
                "floor_id": camera.floor_id, "source_type": camera.source_type, "source": source,
                "regions": camera.regions,
            })
    return {"cameras": result}


@router.post("/internal/vision/heartbeat", status_code=204)
def vision_heartbeat(body: dict, request: Request, tenant_id: int = Header(..., alias="X-Tenant-ID"), db: Session = Depends(get_db)):
    _require_vision_key(request)
    set_tenant_context(db, tenant_id)
    camera = db.scalar(select(Camera).where(Camera.id == int(body.get("camera_id", 0)), Camera.tenant_id == tenant_id))
    if camera:
        camera.last_seen_at = now_utc()


@router.get("/outlets/{outlet_id}/live-occupancy")
def live_occupancy(outlet_id: int, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    """AI-detected occupancy per table. Unvalidated: shown as a hint, not as business truth."""
    set_tenant_context(db, principal.tenant_id)
    require_outlet_access(db, principal, outlet_id)
    cameras = list(db.scalars(select(Camera).where(
        Camera.tenant_id == principal.tenant_id, Camera.restaurant_id == outlet_id, Camera.enabled.is_(True))))
    monitored = {r["table_id"] for c in cameras for r in (c.regions or [])}
    cutoff = now_utc().timestamp() - 120
    ai_online = any(c.last_seen_at and c.last_seen_at.timestamp() >= cutoff for c in cameras)
    latest: dict[int, Observation] = {}
    rows = db.scalars(select(Observation).where(
        Observation.tenant_id == principal.tenant_id, Observation.restaurant_id == outlet_id,
        Observation.observation_type.in_(("TABLE_OCCUPIED", "TABLE_FREE", "TABLE_UNKNOWN")),
    ).order_by(Observation.id.desc()).limit(2000))
    for row in rows:
        if row.table_id is not None and row.table_id not in latest:
            latest[row.table_id] = row
    tables = []
    for table in db.scalars(select(DiningTable).where(DiningTable.tenant_id == principal.tenant_id, DiningTable.restaurant_id == outlet_id)):
        obs = latest.get(table.id)
        if table.id not in monitored:
            state = "unmonitored"
        elif not ai_online or obs is None or obs.observation_type == "TABLE_UNKNOWN":
            state = "unknown"
        else:
            state = "occupied" if obs.observation_type == "TABLE_OCCUPIED" else "free"
        tables.append({"table_id": table.id, "state": state, "since": obs.created_at.isoformat() if obs and state in ("occupied", "free") else None})
    return {"ai_online": ai_online, "tables": tables}


@router.websocket("/ws/outlets/{outlet_id}")
async def outlet_events(websocket: WebSocket, outlet_id: int):
    token = websocket.cookies.get("restaurant_session")
    claims = decode_access_token(token) if token else None
    if not claims:
        await websocket.close(code=4401, reason="Authentication required")
        return
    try:
        tenant_id, user_id = int(claims["tenant_id"]), int(claims["sub"])
    except (KeyError, ValueError, TypeError):
        await websocket.close(code=4401, reason="Invalid session")
        return
    from app.auth.dependencies import has_outlet_access

    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        user = db.scalar(select(User).where(User.id == user_id, User.tenant_id == tenant_id, User.is_active.is_(True)))
        outlet = db.scalar(select(Restaurant).where(Restaurant.id == outlet_id, Restaurant.tenant_id == tenant_id))
        if not user or not outlet or not has_outlet_access(
            db, Principal(user.id, tenant_id, user.role, user.email), outlet_id,
        ):
            await websocket.close(code=4403, reason="Outlet access denied")
            return
    await websocket.accept()
    try:
        async with redis_client.pubsub() as pubsub:
            await pubsub.subscribe(f"tenant:{tenant_id}:restaurant:{outlet_id}")
            async for message in pubsub.listen():
                if message.get("type") == "message":
                    await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        return
    except Exception:
        await websocket.close(code=1011, reason="Realtime service unavailable")

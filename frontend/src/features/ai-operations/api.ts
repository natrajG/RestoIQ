import { api } from "../../shared/api/client";

export interface StaffTask {
  id: number;
  title: string;
  task_type: string;
  target_role: string;
  status: string;
  due_at: string | null;
  table_id: number | null;
  order_id: number | null;
}

export interface Camera {
  id: number;
  name: string;
  enabled: boolean;
  source_type: string;
  last_seen_at: string | null;
  has_reference_image?: boolean;
  floor_id?: number | null;
  regions?: CameraRegion[];
}

export interface FloorCoverage {
  floor_id: number; floor_name: string;
  cameras: { id: number; name: string; zones: number }[];
  tables: { id: number; name: string; cameras: string[] }[];
  uncovered: string[];
}
export interface CameraCoverage { floors: FloorCoverage[]; unassigned_cameras: { id: number; name: string }[] }

export interface CameraRegion { table_id: number; name: string; polygon: [number, number][] }

async function upload(path: string, file: File) {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(`/api/v1${path}`, { method: "POST", body, credentials: "include" });
  if (!response.ok) {
    const detail = await response.json().then((b: { detail?: string }) => b.detail).catch(() => undefined);
    throw new Error(typeof detail === "string" ? detail : `Upload failed (${response.status})`);
  }
}

export interface LiveOccupancy { ai_online: boolean; tables: { table_id: number; state: "occupied" | "free" | "unknown" | "unmonitored"; since: string | null }[] }

export const operationsApi = {
  liveOccupancy: (outletId: number) => api<LiveOccupancy>(`/outlets/${outletId}/live-occupancy`),
  coverage: (outletId: number) => api<CameraCoverage>(`/outlets/${outletId}/camera-coverage`),
  updateCamera: (outletId: number, id: number, body: { name?: string; floor_id?: number | null }) =>
    api<{ id: number }>(`/outlets/${outletId}/cameras/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  createCamera: (outletId: number, body: { name: string; source_type: "rtsp" | "recording"; stream_url?: string; floor_id?: number }) =>
    api<{ id: number }>(`/outlets/${outletId}/cameras`, { method: "POST", body: JSON.stringify({ ...body, restaurant_id: outletId }) }),
  deleteCamera: (outletId: number, id: number) => api<void>(`/outlets/${outletId}/cameras/${id}`, { method: "DELETE" }),
  saveRegions: (outletId: number, id: number, regions: CameraRegion[]) =>
    api<{ regions: CameraRegion[] }>(`/outlets/${outletId}/cameras/${id}/regions`, { method: "PATCH", body: JSON.stringify({ regions }) }),
  uploadReferenceImage: (outletId: number, id: number, file: File) => upload(`/outlets/${outletId}/cameras/${id}/reference-image`, file),
  uploadRecording: (outletId: number, id: number, file: File) => upload(`/outlets/${outletId}/cameras/${id}/recording`, file),
  tasks: (outletId: number) => api<StaffTask[]>(`/outlets/${outletId}/staff-tasks`),
  cameras: (outletId: number) => api<Camera[]>(`/outlets/${outletId}/cameras`),
  acknowledge: (outletId: number, taskId: number) =>
    api<StaffTask>(`/outlets/${outletId}/staff-tasks/${taskId}/acknowledge`, { method: "POST" }),
  complete: (outletId: number, taskId: number, note = "") =>
    api<StaffTask>(`/outlets/${outletId}/staff-tasks/${taskId}/complete`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
};

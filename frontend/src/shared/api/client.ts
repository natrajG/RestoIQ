export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const CACHE_PREFIX = "restoiq.cache:";
const CACHEABLE = /^\/(auth\/me|outlets|outlets\/\d+\/(menu|tables))$/;

// The offline queue is deliberately kept: unsynced orders must not be lost on logout.
export function clearOfflineData() {
  Object.keys(localStorage).filter((k) => k.startsWith(CACHE_PREFIX)).forEach((k) => localStorage.removeItem(k));
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const isGet = !init?.method || init.method === "GET";
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      ...init,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
    });
  } catch (error) {
    // Network is down: fall back to the last copy of the few screens needed to keep billing
    const cached = isGet && CACHEABLE.test(path) ? localStorage.getItem(CACHE_PREFIX + path) : null;
    if (cached) return JSON.parse(cached) as T;
    throw error;
  }
  if (!response.ok) {
    const body = await response.json().catch(() => undefined) as { detail?: string | { loc?: unknown[]; msg: string }[] } | undefined;
    const detail = Array.isArray(body?.detail)
      ? body.detail.map((item) => `${String(item.loc?.[item.loc.length - 1] ?? "").replace(/_/g, " ")}: ${item.msg}`).join("; ")
      : body?.detail;
    throw new ApiError(detail ?? `Request failed (${response.status})`, response.status);
  }
  if (response.status === 204) return undefined as T;
  const data = await response.json() as T;
  if (isGet && CACHEABLE.test(path)) {
    try { localStorage.setItem(CACHE_PREFIX + path, JSON.stringify(data)); } catch { /* storage full */ }
  }
  return data;
}

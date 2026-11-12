import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { notification } from "antd";
import { useLocation, useNavigate } from "react-router-dom";
import { operationsApi } from "./api";

export const ALERT_ROLES = ["kitchen", "waiter", "server", "cashier", "cleaner", "cleaning"];
const KEY = "new-tasks";
const WATCHING = ["/tasks", "/kitchen"]; // staff already looking at the list don't need a popup

/** One grouped popup for new tasks of the signed-in role. Several tasks arriving together or while it is open update the same popup, so it never stacks. */
export function TaskAlerts({ outletId, openTo }: { outletId: number; openTo: string }) {
  const navigate = useNavigate();
  const path = useLocation().pathname;
  const seen = useRef<Set<number> | null>(null);
  const batch = useRef<string[]>([]);
  const q = useQuery({ queryKey: ["task-alerts", outletId], queryFn: () => operationsApi.tasks(outletId), refetchInterval: 5000 });

  useEffect(() => {
    seen.current = null; // a different outlet starts fresh without alerting for existing tasks
    batch.current = [];
    notification.destroy(KEY);
  }, [outletId]);

  useEffect(() => {
    if (!q.data) return;
    const pending = q.data.filter((t) => t.status === "pending");
    if (seen.current === null) {
      seen.current = new Set(pending.map((t) => t.id));
      return;
    }
    const fresh = pending.filter((t) => !seen.current!.has(t.id));
    fresh.forEach((t) => seen.current!.add(t.id));
    if (!fresh.length) return;
    if (WATCHING.includes(path)) return;
    batch.current = [...batch.current, ...fresh.map((t) => t.title)];
    const shown = batch.current.slice(-3);
    const extra = batch.current.length - shown.length;
    notification.info({
      key: KEY, placement: "bottomRight", duration: 8, showProgress: true, pauseOnHover: true,
      message: batch.current.length === 1 ? "New task" : `${batch.current.length} new tasks`,
      description: <div>{shown.map((s, i) => <div key={i}>{s}</div>)}{extra > 0 && <div>+{extra} more</div>}<div style={{ marginTop: 4, opacity: 0.65 }}>Tap to open</div></div>,
      onClick: () => { notification.destroy(KEY); batch.current = []; navigate(openTo); },
      onClose: () => { batch.current = []; },
    });
  }, [q.data, navigate, path, openTo]);

  return null;
}

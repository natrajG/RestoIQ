import { useEffect, useState } from "react";
import { ApiError, api } from "./api/client";
import { getAutoKot, printQueuedKot } from "../features/pos/printing";
import type { OfflineCharges, OfflineLine } from "./offlineBill";

const KEY = "restoiq.queue";

export interface OfflinePayment { key: string; method: string; amount: string; reference?: string }

export interface QueuedOrder {
  key: string;
  outletId: number;
  body: unknown;
  label: string;
  createdAt: string;
  error?: string;
  restaurant?: string;
  orderType?: string;
  contact?: string;
  lines?: OfflineLine[];
  charges?: OfflineCharges;
  payments?: OfflinePayment[];
  orderId?: number;
  tableName?: string;
  tenantId?: number;
  /** Set for items added to an already-open order; the entry then posts to /orders/{id}/items. */
  addToOrderId?: number;
  kotPrinted?: boolean;
}

export const isNetworkError = (e: unknown) => e instanceof TypeError;

let owner: number | undefined;

/** Scopes the queue to the signed-in restaurant, so another restaurant on the same device never sees or sends it. */
export function setQueueOwner(tenantId: number) {
  owner = tenantId;
}

function readAll(): QueuedOrder[] {
  try { return JSON.parse(localStorage.getItem(KEY) ?? "[]") as QueuedOrder[]; } catch { return []; }
}

export function readQueue(): QueuedOrder[] {
  return readAll().filter((q) => q.tenantId === undefined || q.tenantId === owner);
}

function writeQueue(mine: QueuedOrder[]) {
  const others = readAll().filter((q) => !(q.tenantId === undefined || q.tenantId === owner));
  localStorage.setItem(KEY, JSON.stringify([...others, ...mine]));
  window.dispatchEvent(new Event("restoiq-queue"));
}

export function enqueueOrder(outletId: number, body: unknown, label: string, key: string, extra: Partial<QueuedOrder> = {}) {
  writeQueue([...readQueue(), { ...extra, key, outletId, body, label, tenantId: owner, createdAt: new Date().toISOString() }]);
}

export function addOfflinePayment(key: string, payment: Omit<OfflinePayment, "key">) {
  writeQueue(readQueue().map((q) => (q.key === key ? { ...q, payments: [...(q.payments ?? []), { ...payment, key: crypto.randomUUID() }] } : q)));
}

export function markKotPrinted(key: string) {
  writeQueue(readQueue().map((q) => (q.key === key ? { ...q, kotPrinted: true } : q)));
}

export function discardQueued(key: string) {
  writeQueue(readQueue().filter((q) => q.key !== key));
}

let syncing = false;

/** One tab at a time may sync; the Web Lock also covers other tabs, which the flag above cannot. */
export async function syncQueue(): Promise<number> {
  if (syncing) return 0;
  if (!navigator.locks) return runSync();
  return (await navigator.locks.request("restoiq-sync", { ifAvailable: true }, async (lock) => (lock ? runSync() : 0))) ?? 0;
}

/** Sends queued orders in order. The saved key is the Idempotency-Key, so a retry never creates a duplicate. */
async function runSync(): Promise<number> {
  if (syncing) return 0;
  syncing = true;
  let sent = 0;
  try {
    const statusOf = async (_outletId: number, orderId: number) => {
      try { return (await api<{ status: string }>(`/orders/${orderId}`)).status; } catch (e) {
        if (e instanceof ApiError && e.status === 404) return undefined;
        throw e;
      }
    };
    const fail = (key: string, msg: string) => writeQueue(readQueue().map((q) => (q.key === key ? { ...q, error: msg } : q)));
    for (const item of readQueue().filter((q) => !q.error)) {
      try {
        if (item.addToOrderId) {
          await api(`/orders/${item.addToOrderId}/items`, { method: "POST", headers: { "Idempotency-Key": item.key }, body: JSON.stringify(item.body) });
          sent += 1;
          if (!item.kotPrinted && getAutoKot()) printQueuedKot(item);
          discardQueued(item.key);
          continue;
        }
        let orderId = item.orderId;
        if (!orderId) {
          let created: { id: number };
          try {
            created = await api<{ id: number }>(`/outlets/${item.outletId}/orders`, { method: "POST", headers: { "Idempotency-Key": item.key }, body: JSON.stringify(item.body) });
          } catch (e) {
            // Another waiter opened this table first: add our items to that bill as a new KOT.
            if (!(e instanceof ApiError && e.status === 409 && /Table is not available/.test(e.message))) throw e;
            const body = item.body as { table_id?: number; items: unknown[] };
            const rows = await api<{ id: number; table_id: number | null; status: string }[]>(`/outlets/${item.outletId}/orders?limit=200`);
            const open = rows.find((r) => r.table_id === body.table_id && !["paid", "completed", "cancelled", "refunded"].includes(r.status));
            if (!open) throw e;
            await api(`/orders/${open.id}/items`, { method: "POST", headers: { "Idempotency-Key": item.key }, body: JSON.stringify({ items: body.items }) });
            created = open;
          }
          sent += 1;
          orderId = created.id;
          if (!item.kotPrinted && getAutoKot()) { printQueuedKot(item); markKotPrinted(item.key); }
          if (!item.payments?.length) { discardQueued(item.key); continue; }
          writeQueue(readQueue().map((q) => (q.key === item.key ? { ...q, orderId } : q)));
        }
        // Cash taken offline is recorded once the order is handed over, so the kitchen still sees it until then
        const status = await statusOf(item.outletId, orderId);
        if (status === "served" || status === "bill_requested") {
          for (const p of item.payments ?? []) {
            await api(`/orders/${orderId}/payments`, { method: "POST", headers: { "Idempotency-Key": p.key }, body: JSON.stringify({ method: p.method, amount: p.amount, reference: p.reference }) });
          }
          discardQueued(item.key);
        } else if (!status || ["paid", "completed", "cancelled", "refunded"].includes(status)) {
          fail(item.key, `Order is ${status ?? "not found"}; offline payment was not recorded. Check the cash against the Orders screen.`);
        }
      } catch (e) {
        if (isNetworkError(e)) break;
        if (e instanceof ApiError && e.status === 401) break;
        fail(item.key, (e as Error).message);
      }
    }
  } finally {
    syncing = false;
  }
  return sent;
}

export function useOnline() {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(true), off = () => setOnline(false);
    window.addEventListener("online", on); window.addEventListener("offline", off);
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, []);
  return online;
}

export function useQueue() {
  const [queue, setQueue] = useState(readQueue);
  useEffect(() => {
    const h = () => setQueue(readQueue());
    window.addEventListener("restoiq-queue", h);
    return () => window.removeEventListener("restoiq-queue", h);
  }, []);
  return queue;
}

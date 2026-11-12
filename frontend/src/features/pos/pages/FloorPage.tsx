import { useQuery } from "@tanstack/react-query";
import { Alert, Card, Input, Segmented, Select, Skeleton, Space, Tag, Typography } from "antd";
import { useState } from "react";
import { operationsApi } from "../../ai-operations/api";
import { posApi, tableLiveApi } from "../api";

const statusColor: Record<string, string> = {
  FREE: "green",
  READY: "cyan",
  OCCUPIED: "blue",
  DIRTY: "orange",
  CLEANING: "gold",
  RESERVED: "purple",
  BILLING: "red",
};

export function FloorPage({ outletId }: { outletId: number }) {
  const tables = useQuery({ queryKey: ["tables", outletId], queryFn: () => posApi.tables(outletId), refetchInterval: 15000 });
  const live = useQuery({ queryKey: ["live-occupancy", outletId], queryFn: () => operationsApi.liveOccupancy(outletId), refetchInterval: 5000 });
  const liveOrders = useQuery({ queryKey: ["table-live", outletId], queryFn: () => tableLiveApi.get(outletId), refetchInterval: 15000 });
  const [q, setQ] = useState("");
  const [state, setState] = useState<"all" | "free" | "running" | "bill">("all");
  const [waiter, setWaiter] = useState<string>();
  const info = (id: number) => liveOrders.data?.[String(id)];
  const all = tables.data ?? [];
  const count = { free: all.filter((t) => ["FREE", "READY"].includes(t.status)).length, running: all.filter((t) => info(t.id) && t.status !== "BILLING").length, bill: all.filter((t) => t.status === "BILLING").length };
  const waiters = [...new Set(Object.values(liveOrders.data ?? {}).map((o) => o.waiter).filter(Boolean))] as string[];
  const shown = all.filter((t) => t.name.toLowerCase().includes(q.trim().toLowerCase())
    && (state === "all" || (state === "free" ? ["FREE", "READY"].includes(t.status) : state === "bill" ? t.status === "BILLING" : !!info(t.id) && t.status !== "BILLING"))
    && (!waiter || info(t.id)?.waiter === waiter));
  const aiByTable = new Map((live.data?.tables ?? []).map((t) => [t.table_id, t]));
  const aiTag = (id: number) => {
    const ai = aiByTable.get(id);
    if (!ai || ai.state === "unmonitored") return <Tag>AI: no camera</Tag>;
    if (ai.state === "unknown") return <Tag color="default">AI: no signal</Tag>;
    return ai.state === "occupied" ? <Tag color="red">AI: people seated</Tag> : <Tag color="green">AI: empty</Tag>;
  };
  return (
    <div className="page">
      <div className="page-heading"><div><Typography.Title level={2}>Live floor</Typography.Title><Typography.Paragraph type="secondary">Table availability, cleaning and service status. AI occupancy comes from your cameras and is a live hint, not yet validated.</Typography.Paragraph></div></div>
      {live.data && !live.data.ai_online && (live.data.tables.some((t) => t.state !== "unmonitored")) && <Alert type="warning" showIcon style={{ marginBottom: 12 }} message="AI detection is offline" description="No camera has reported in the last 2 minutes." />}
      {tables.isError && <Alert type="error" showIcon message="Unable to load table status" />}
      <Space wrap style={{ marginBottom: 12 }}>
        <Input.Search allowClear placeholder="Search table" style={{ width: 200 }} onChange={(e) => setQ(e.target.value)} />
        <Segmented value={state} onChange={(v) => setState(v as typeof state)} options={[{ value: "all", label: `All ${all.length}` }, { value: "free", label: `Free ${count.free}` }, { value: "running", label: `Running ${count.running}` }, { value: "bill", label: `Bill printed ${count.bill}` }]} />
        <Select allowClear placeholder="Waiter" style={{ width: 150 }} value={waiter} onChange={setWaiter} options={waiters.map((w) => ({ value: w, label: w }))} />
      </Space>
      {tables.isLoading ? <Skeleton active /> : (
        <div className="floor-grid">
          {shown.map((table) => (
            <Card key={table.id} className="floor-table">
              <div className="floor-table-top"><Typography.Title level={4}>{table.name}</Typography.Title><Tag color={statusColor[table.status] ?? "default"}>{table.status}</Tag></div>
              <Typography.Text type="secondary">{table.seats} seats</Typography.Text>
              {info(table.id) && <div style={{ marginTop: 6 }}><b>₹{Number(info(table.id)!.amount).toFixed(2)}</b> · {info(table.id)!.minutes} min{info(table.id)!.waiter ? ` · ${info(table.id)!.waiter}` : ""}{info(table.id)!.covers ? ` · ${info(table.id)!.covers} guests` : ""}</div>}<div style={{ marginTop: 8 }}>{aiTag(table.id)}</div>
            </Card>
          ))}
          {!tables.data?.length && !tables.isError && <div className="empty-note">No tables configured yet.</div>}
        </div>
      )}
    </div>
  );
}

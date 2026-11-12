import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, message, Empty, Skeleton, Tag, Typography } from "antd";
import { orderApi, posApi, type OrderEvent } from "../api";
import { printKot } from "../printing";

const NEXT: Record<string, { label: string; event: OrderEvent }> = {
  submitted: { label: "Start preparing", event: "PREPARATION_STARTED" },
  accepted: { label: "Start preparing", event: "PREPARATION_STARTED" },
  preparing: { label: "Food ready", event: "FOOD_READY" },
};

export function KitchenPage({ outletId, restaurantName = "Restaurant" }: { outletId: number; restaurantName?: string }) {
  const tables = useQuery({ queryKey: ["tables", outletId], queryFn: () => posApi.tables(outletId) });
  const tableName = (id: number | null) => (id ? tables.data?.find((t) => t.id === id)?.name ?? `Table ${id}` : null);
  const queue = useQuery({ queryKey: ["kitchen", outletId], queryFn: () => posApi.kitchen(outletId), refetchInterval: 10000 });
  const client = useQueryClient();
  const advance = useMutation({
    mutationFn: ({ id, event }: { id: number; event: OrderEvent }) => orderApi.event(id, event),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ["kitchen", outletId] }); void client.invalidateQueries({ queryKey: ["orders", outletId] }); },
    onError: (e: Error) => message.error(e.message),
  });
  return (
    <div className="page">
      <div className="page-heading"><div><Typography.Title level={2}>Kitchen queue</Typography.Title><Typography.Paragraph type="secondary">Orders requiring preparation or pickup follow-up.</Typography.Paragraph></div></div>
      {queue.error && <Alert type="error" showIcon message="Kitchen queue could not be refreshed" />}
      {queue.isLoading ? <Skeleton active /> : queue.data?.length ? (
        <div className="floor-grid">
          {queue.data.map((order) => (
            <Card key={order.id} title={`${order.order_type === "dine_in" ? (tableName(order.table_id) ?? "Dine-in") : order.order_type.toUpperCase()} · ${order.order_number}`} extra={<Tag color={order.status === "ready" ? "green" : "blue"}>{order.status}</Tag>}>
              {order.status === "ready" && <Typography.Text strong style={{ color: "#389e0d" }}>READY: take to {order.order_type === "dine_in" ? (tableName(order.table_id) ?? "the table") : order.order_type.toUpperCase()}</Typography.Text>}
              {order.remark && <div><Typography.Text type="warning">{order.remark}</Typography.Text></div>}
              {[...new Set(order.items.map((i) => i.kot_no))].sort().map((kot) => (
                <div key={kot}>
                  <Typography.Text type="secondary">KOT {kot}</Typography.Text>{" "}<Button size="small" type="link" onClick={() => printKot(order, kot, tableName(order.table_id), restaurantName, true)}>Reprint</Button>
                  {order.items.filter((i) => i.kot_no === kot).map((item) => (
                    <div className="provider-row" key={item.id} style={item.status === "cancelled" ? { textDecoration: "line-through", opacity: 0.5 } : undefined}>
                      <span>{item.name}{item.addons?.length ? ` + ${item.addons.map((a) => a.name).join(", ")}` : ""}{item.notes ? <Typography.Text type="warning"> · {item.notes}</Typography.Text> : null}</span><b>× {item.quantity}</b>
                    </div>))}
                </div>))}
            {NEXT[order.status] && <Button type="primary" block style={{ marginTop: 8 }} loading={advance.isPending} onClick={() => advance.mutate({ id: order.id, event: NEXT[order.status].event })}>{NEXT[order.status].label}</Button>}
              {order.status === "ready" && <Typography.Text type="secondary">Waiting for a waiter to pick up.</Typography.Text>}
            </Card>
          ))}
        </div>
      ) : <Card><Empty description="No active kitchen orders." /></Card>}
    </div>
  );
}

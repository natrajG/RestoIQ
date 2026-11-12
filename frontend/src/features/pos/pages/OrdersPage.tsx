import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Form, InputNumber, Input, Modal, Select, Space, Switch, Table, Tag, Typography, message } from "antd";
import { useState } from "react";
import { menuApi, orderApi, posApi, type OrderEvent, type OrderItemRow, type OrderRow } from "../api";
import { BillModal } from "../components/BillModal";
import { enqueueOrder, isNetworkError } from "../../../shared/offlineQueue";
import { getAutoKot, printKot, printKotCancel, printQueuedKot } from "../printing";

const COLORS: Record<string, string> = { submitted: "blue", preparing: "orange", ready: "green", picked_up: "cyan", served: "purple", bill_requested: "gold", paid: "green", completed: "default", cancelled: "red", refunded: "red" };
const NEXT: Record<string, { label: string; event: OrderEvent }> = {
  ready: { label: "Picked up", event: "FOOD_PICKED_UP" },
  picked_up: { label: "Mark served", event: "FOOD_DELIVERED" },
  served: { label: "Request bill", event: "BILL_REQUESTED" },
};

const nextLabel = (o: { status: string; order_type: string }) =>
  o.order_type === "delivery" ? ({ ready: "Out for delivery", picked_up: "Delivered" } as Record<string, string>)[o.status] ?? NEXT[o.status].label
  : o.order_type === "takeaway" ? ({ ready: "Handed over", picked_up: "Handed over" } as Record<string, string>)[o.status] ?? NEXT[o.status].label
  : NEXT[o.status].label;

const OPEN = ["submitted", "accepted", "preparing", "ready", "picked_up", "served", "bill_requested"];

export function OrdersPage({ outletId, currency, restaurantName = "Restaurant" }: { outletId: number; currency: string; restaurantName?: string }) {
  const client = useQueryClient();
  const [billId, setBillId] = useState<number | null>(null);
  const [payFor, setPayFor] = useState<OrderRow | null>(null);
  const [addFor, setAddFor] = useState<OrderRow | null>(null);
  const [cancelling, setCancelling] = useState<{ order: OrderRow; item: OrderItemRow } | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [chargeFor, setChargeFor] = useState<OrderRow | null>(null);
  const [moving, setMoving] = useState<{ order: OrderRow; mode: "shift" | "merge" } | null>(null);
  const [f, setF] = useState<{ q: string; status?: string; staff?: string; type?: string }>({ q: "" });
  const [moveTo, setMoveTo] = useState<number>();
  const [splitFor, setSplitFor] = useState<OrderRow | null>(null);
  const [splitQty, setSplitQty] = useState<Record<number, number>>({});
  const [chargeForm] = Form.useForm();
  const [freeFor, setFreeFor] = useState<OrderRow | null>(null);
  const [freeIds, setFreeIds] = useState<number[]>([]);
  const [freeReason, setFreeReason] = useState("");
  const [voiding, setVoiding] = useState<OrderRow | null>(null);
  const [voidReason, setVoidReason] = useState("");
  const [lines, setLines] = useState<{ menu_item_id?: number; quantity: number; notes?: string; variant_id?: number; addon_ids?: number[] }[]>([{ quantity: 1 }]);
  const [form] = Form.useForm();
  const menu = useQuery({ queryKey: ["menu", outletId], queryFn: () => posApi.menu(outletId), enabled: !!addFor });
  const tables = useQuery({ queryKey: ["tables", outletId], queryFn: () => posApi.tables(outletId) });
  const tableName = (id: number | null) => (id ? tables.data?.find((t) => t.id === id)?.name ?? `Table ${id}` : null);
  const orders = useQuery({ queryKey: ["orders", outletId], queryFn: () => orderApi.list(outletId), refetchInterval: 10000 });
  const refresh = () => { void client.invalidateQueries({ queryKey: ["orders", outletId] }); void client.invalidateQueries({ queryKey: ["tables", outletId] }); void client.invalidateQueries({ queryKey: ["kitchen", outletId] }); };
  const onError = (e: Error) => message.error(e.message);
  const event = useMutation({ mutationFn: ({ id, ev }: { id: number; ev: OrderEvent }) => orderApi.event(id, ev), onSuccess: refresh, onError });
  const add = useMutation({
    mutationFn: async () => {
      const items = lines.filter((l) => l.menu_item_id).map((l) => ({ menu_item_id: l.menu_item_id!, quantity: l.quantity, notes: l.notes?.trim() || undefined, variant_id: l.variant_id, addon_ids: l.addon_ids }));
      const key = crypto.randomUUID();
      try {
        return await orderApi.addItems(addFor!.id, items, key);
      } catch (e) {
        if (!isNetworkError(e)) throw e;
        // Saved on this device; the key makes the later send safe even if this request did reach the server.
        const queued = items.map((i) => {
          const m = menu.data?.find((x) => x.id === i.menu_item_id);
          return { name: m?.name ?? `Item ${i.menu_item_id}`, qty: i.quantity, unitPaise: Math.round(Number(m?.price ?? 0) * 100), rate: Number(m?.tax_rate ?? 0) };
        });
        const extra = { restaurant: restaurantName, orderType: addFor!.order_type, tableName: tableName(addFor!.table_id) ?? undefined, lines: queued, addToOrderId: addFor!.id };
        const printNow = getAutoKot();
        enqueueOrder(outletId, { items }, `Add ${items.length} item(s) to order ${addFor!.order_number}`, key, { ...extra, kotPrinted: printNow });
        if (printNow) printQueuedKot({ ...extra, key, outletId, body: { items }, label: "", createdAt: new Date().toISOString() });
        return null;
      }
    },
    onSuccess: (updated) => {
      if (!updated) message.warning("Offline: new KOT saved on this device. It reaches the kitchen when the internet is back.");
      else {
        if (getAutoKot()) printKot(updated, Math.max(...updated.items.map((i) => i.kot_no)), tableName(updated.table_id), restaurantName);
        message.success("Sent to the kitchen as a new KOT");
      }
      setAddFor(null); setLines([{ quantity: 1 }]); refresh();
    },
    onError,
  });
  const charges = useMutation({
    mutationFn: (v: { type: "percent" | "fixed" | "none"; value?: number; reason?: string; waive?: boolean; tip?: number }) => orderApi.setCharges(chargeFor!.id, {
      discount_type: v.type === "none" ? null : v.type, discount_value: v.type === "none" ? 0 : v.value ?? 0, discount_reason: v.reason, waive_service_charge: !!v.waive, tip: v.tip ?? 0 }),
    onSuccess: () => { message.success("Bill updated"); void client.invalidateQueries({ queryKey: ["bill"] }); setChargeFor(null); refresh(); },
    onError,
  });
  const move = useMutation({
    mutationFn: () => (moving!.mode === "shift" ? orderApi.shift(moving!.order.id, moveTo!) : orderApi.merge(moving!.order.id, moveTo!)),
    onSuccess: () => { message.success(moving!.mode === "shift" ? "Table changed" : "Orders merged"); setMoving(null); setMoveTo(undefined); refresh(); },
    onError,
  });
  const split = useMutation({
    mutationFn: () => orderApi.split(splitFor!.id, Object.entries(splitQty).filter(([, q]) => q > 0).map(([id, quantity]) => ({ item_id: Number(id), quantity }))),
    onSuccess: (r) => { message.success(`New bill ${r.new.order_number} created`); setSplitFor(null); setSplitQty({}); refresh(); },
    onError,
  });
  const complimentary = useMutation({
    mutationFn: () => orderApi.complimentary(freeFor!.id, freeIds, freeReason.trim()),
    onSuccess: () => { message.success("Bill updated"); void client.invalidateQueries({ queryKey: ["bill"] }); setFreeFor(null); refresh(); },
    onError,
  });
  const voidOrder = useMutation({
    mutationFn: () => orderApi.void(voiding!.id, voidReason.trim()),
    onSuccess: () => { message.success("Order voided"); setVoiding(null); setVoidReason(""); refresh(); },
    onError,
  });
  const cancel = useMutation({
    mutationFn: () => orderApi.cancelItem(cancelling!.order.id, cancelling!.item.id, cancelReason),
    onSuccess: () => { message.success("Item cancelled"); if (getAutoKot() && cancelling) printKotCancel(cancelling.order, { ...cancelling.item, cancel_reason: cancelReason.trim() }, tableName(cancelling.order.table_id), restaurantName); setCancelling(null); setCancelReason(""); refresh(); },
    onError,
  });
  const bill = useQuery({ queryKey: ["bill", payFor?.id], queryFn: () => menuApi.bill(payFor!.id), enabled: !!payFor });
  const outstanding = bill.data ? Number(bill.data.payable) - bill.data.payments.reduce((t, p) => t + Number(p.amount), 0) : 0;
  const pay = useMutation({
    mutationFn: (v: { method: string; amount: number; reference?: string }) => orderApi.pay(payFor!.id, { method: v.method, amount: v.amount.toFixed(2), reference: v.reference || undefined }, crypto.randomUUID()),
    onSuccess: (r) => { message.success(r.order_paid ? "Payment complete" : "Part payment recorded"); void client.invalidateQueries({ queryKey: ["bill"] }); setPayFor(null); form.resetFields(); refresh(); },
    onError,
  });
  return (
    <div className="page">
      <div className="page-heading"><div>
        <Typography.Title level={2}>Orders & billing</Typography.Title>
        <Typography.Paragraph type="secondary">Follow each order from kitchen to table, then take payment and release the table.</Typography.Paragraph>
      </div></div>
      {(() => {
        const adv = (orders.data ?? []).filter((o) => o.scheduled_for && OPEN.includes(o.status) && new Date(o.scheduled_for).toDateString() === new Date().toDateString())
          .sort((a, b) => a.scheduled_for!.localeCompare(b.scheduled_for!));
        return adv.length > 0 && <Alert type="info" showIcon style={{ marginBottom: 12 }} message={`Today's advance orders (${adv.length})`}
          description={adv.map((o) => `${new Date(o.scheduled_for!).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} · ${o.order_number} · ${o.contact_name ?? o.contact_phone ?? o.order_type}`).join("  |  ")} />;
      })()}
      {orders.isError && <Alert type="error" showIcon message="Orders could not be loaded" />}
      <Space wrap style={{ marginBottom: 12 }}>
        <Input.Search allowClear placeholder="Search bill no, customer, table" style={{ width: 260 }} onSearch={(q) => setF({ ...f, q: q.trim().toLowerCase() })} />
        <Select allowClear placeholder="Status" style={{ width: 150 }} value={f.status} onChange={(status) => setF({ ...f, status })} options={["open", "paid", "completed", "cancelled"].map((v) => ({ value: v, label: v }))} />
        <Select allowClear placeholder="Order type" style={{ width: 150 }} value={f.type} onChange={(type) => setF({ ...f, type })} options={["dine_in", "takeaway", "delivery"].map((v) => ({ value: v, label: v.replace("_", " ") }))} />
        <Select allowClear placeholder="Staff" style={{ width: 160 }} value={f.staff} onChange={(staff) => setF({ ...f, staff })} options={[...new Set((orders.data ?? []).map((o) => o.staff_name).filter(Boolean))].map((v) => ({ value: v as string, label: v as string }))} />
      </Space>
      <Table<OrderRow> rowKey="id" loading={orders.isLoading} dataSource={(orders.data ?? []).filter((o) =>
        (!f.status || (f.status === "open" ? OPEN.includes(o.status) : o.status === f.status)) && (!f.type || o.order_type === f.type) && (!f.staff || o.staff_name === f.staff)
        && (!f.q || [o.order_number, o.contact_name, o.contact_phone, tableName(o.table_id)].filter(Boolean).join(" ").toLowerCase().includes(f.q)))}
        expandable={{ expandedRowRender: (o) => (
          <div>
            {[...new Set(o.items.map((i) => i.kot_no))].sort().map((kot) => (
              <div key={kot} style={{ marginBottom: 8 }}>
                <Typography.Text strong>KOT {kot}</Typography.Text>{" "}<Button size="small" type="link" onClick={() => printKot(o, kot, tableName(o.table_id), restaurantName, true)}>Reprint KOT</Button>
                {o.items.filter((i) => i.kot_no === kot).map((i) => (
                  <div key={i.id} className="provider-row" style={i.status === "cancelled" ? { textDecoration: "line-through", opacity: 0.55 } : undefined}>
                    <span>{i.name}{i.complimentary ? " (complimentary)" : ""}{i.addons?.length ? ` + ${i.addons.map((a) => a.name).join(", ")}` : ""} × {i.quantity}{i.notes ? ` · ${i.notes}` : ""}{i.cancel_reason ? ` (cancelled: ${i.cancel_reason})` : ""}</span>
                    {i.status === "active" && OPEN.includes(o.status) && <Button size="small" danger onClick={() => setCancelling({ order: o, item: i })}>Cancel item</Button>}
                    {i.status === "cancelled" && <Button size="small" type="link" onClick={() => printKotCancel(o, i, tableName(o.table_id), restaurantName)}>Print cancel slip</Button>}
                  </div>))}
              </div>))}
          </div>) }}
        pagination={{ pageSize: 15, hideOnSinglePage: true }}
        columns={[
          { title: "Bill no", dataIndex: "order_number", render: (n: string, o) => (<span>{n}{o.order_type !== "dine_in" && <Tag color="purple" style={{ marginLeft: 6 }}>{o.order_type}</Tag>}
            {(o.staff_name || o.covers || o.remark) && <div><Typography.Text type="secondary">{[o.staff_name && `by ${o.staff_name}`, o.covers && `${o.covers} guests`, o.remark && `“${o.remark}”`].filter(Boolean).join(" · ")}</Typography.Text></div>}
            {o.scheduled_for && <div><Tag color="geekblue">Scheduled {new Date(o.scheduled_for).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}</Tag></div>}
            {Number(o.complimentary_total) > 0 && <div><Typography.Text type="secondary">Complimentary {Number(o.complimentary_total).toFixed(2)}{o.complimentary_reason ? ` · ${o.complimentary_reason}` : ""}</Typography.Text></div>}
            {o.order_type !== "dine_in" && <div><Typography.Text type="secondary">{[o.contact_name, o.contact_phone].filter(Boolean).join(" · ")}{o.delivery_address ? ` · ${o.delivery_address}` : ""}</Typography.Text></div>}</span>) },
          { title: "Items", dataIndex: "items", render: (items: OrderRow["items"]) => items.filter((i) => i.status === "active").map((i) => `${i.name}${i.addons?.length ? ` + ${i.addons.map((a) => a.name).join(", ")}` : ""} × ${i.quantity}`).join(", ") },
          { title: `Total (${currency})`, dataIndex: "total", render: (v: string, o) => <span>{Number(v).toFixed(2)}{Number(o.tip) > 0 ? <Typography.Text type="secondary"> + tip {Number(o.tip).toFixed(2)}</Typography.Text> : null}</span> },
          { title: "Status", dataIndex: "status", render: (s: string) => <Tag color={COLORS[s]}>{s.replace("_", " ")}</Tag> },
          { title: "Actions", render: (_, o) => (
            <Space wrap>
              {OPEN.includes(o.status) && <Button size="small" onClick={() => setAddFor(o)}>Add items</Button>}
              {OPEN.includes(o.status) && <Button size="small" onClick={() => setChargeFor(o)}>Discount / tip</Button>}
              {NEXT[o.status] && !(o.order_type !== "dine_in" && o.status === "served") && <Button size="small" type="primary" loading={event.isPending} onClick={() => event.mutate({ id: o.id, ev: NEXT[o.status].event })}>{nextLabel(o)}</Button>}
              {["served", "bill_requested"].includes(o.status) && <Button size="small" type="primary" onClick={() => setPayFor(o)}>Take payment</Button>}
              {o.status === "paid" && <Button size="small" onClick={() => event.mutate({ id: o.id, ev: "CUSTOMER_DEPARTED" })}>{o.order_type === "dine_in" ? "Customer left" : "Close order"}</Button>}
              {o.order_type === "dine_in" && o.table_id && OPEN.includes(o.status) && <Button size="small" onClick={() => setMoving({ order: o, mode: "shift" })}>Shift table</Button>}
              {o.order_type === "dine_in" && o.table_id && OPEN.includes(o.status) && <Button size="small" onClick={() => setMoving({ order: o, mode: "merge" })}>Merge</Button>}
              {o.table_id && OPEN.includes(o.status) && o.items.filter((i) => i.status === "active").reduce((n, i) => n + i.quantity, 0) > 1 && <Button size="small" onClick={() => { setSplitFor(o); setSplitQty({}); }}>Split bill</Button>}
              {OPEN.includes(o.status) && !["paid"].includes(o.status) && <Button size="small" onClick={() => { setFreeFor(o); setFreeIds(o.items.filter((i) => i.complimentary).map((i) => i.id)); setFreeReason(o.complimentary_reason ?? ""); }}>Complimentary</Button>}
              {OPEN.includes(o.status) && <Button size="small" danger onClick={() => setVoiding(o)}>Void</Button>}
              <Button size="small" onClick={() => setBillId(o.id)}>Bill</Button>
            </Space>) },
        ]} />
      <Modal open={!!splitFor} title={`Split ${splitFor?.order_number ?? ""} into a separate bill`} okText="Create new bill" confirmLoading={split.isPending}
        okButtonProps={{ disabled: !Object.values(splitQty).some((q) => q > 0) }} onCancel={() => setSplitFor(null)} onOk={() => split.mutate()} destroyOnClose>
        <Typography.Paragraph type="secondary">Choose how many of each item move to the new bill (same table, its own invoice number). A percentage discount is copied; a fixed discount stays on the original. Not possible once a payment is recorded.</Typography.Paragraph>
        {(splitFor?.items ?? []).filter((i) => i.status === "active").map((i) => (
          <div key={i.id} className="provider-row"><span>{i.name} <Typography.Text type="secondary">(on bill: {i.quantity})</Typography.Text></span>
            <InputNumber min={0} max={i.quantity} value={splitQty[i.id] ?? 0} onChange={(q) => setSplitQty((m) => ({ ...m, [i.id]: q ?? 0 }))} /></div>))}
      </Modal>
      <Modal open={!!moving} title={moving?.mode === "shift" ? `Move ${moving?.order.order_number} to another table` : `Merge ${moving?.order.order_number} into another order`}
        okText={moving?.mode === "shift" ? "Move" : "Merge"} okButtonProps={{ disabled: !moveTo }} confirmLoading={move.isPending}
        onCancel={() => { setMoving(null); setMoveTo(undefined); }} onOk={() => move.mutate()} destroyOnClose>
        {moving?.mode === "merge" && <Typography.Paragraph type="secondary">All items move to the chosen order and this order is closed. Neither order may have a payment yet.</Typography.Paragraph>}
        <Select style={{ width: "100%" }} placeholder={moving?.mode === "shift" ? "Select a free table" : "Select a running order"} value={moveTo} onChange={setMoveTo} showSearch optionFilterProp="label"
          options={moving?.mode === "shift"
            ? (tables.data ?? []).filter((t) => ["FREE", "READY"].includes(t.status)).map((t) => ({ value: t.id, label: `${t.name} · ${t.seats} seats` }))
            : (orders.data ?? []).filter((x) => x.id !== moving?.order.id && x.order_type === "dine_in" && x.table_id && OPEN.includes(x.status)).map((x) => ({ value: x.id, label: `${tableName(x.table_id)} · ${x.order_number}` }))} />
      </Modal>
      <Modal open={!!payFor} title={`Payment · ${payFor?.order_number ?? ""}`} onCancel={() => setPayFor(null)} onOk={() => form.submit()} okText="Record payment" confirmLoading={pay.isPending} destroyOnClose>
        {bill.isLoading ? "Loading…" : (
          <Form form={form} layout="vertical" initialValues={{ method: "cash", amount: outstanding }} key={outstanding} onFinish={(v) => pay.mutate(v)}>
            <Typography.Paragraph>Outstanding: <b>{currency} {outstanding.toFixed(2)}</b></Typography.Paragraph>
            <Form.Item label="Split equally among">
              <Space>
                <InputNumber min={1} max={20} defaultValue={1} onChange={(n) => form.setFieldValue("amount", Math.min(outstanding, Math.ceil((outstanding / (n || 1)) * 100) / 100))} />
                <Typography.Text type="secondary">people — record one payment per person, each can use a different method</Typography.Text>
              </Space>
            </Form.Item>
            <Form.Item name="method" label="Method"><Select options={[{ value: "cash", label: "Cash" }, { value: "upi_external", label: "UPI (customer pays on own app/QR)" }, { value: "card_external", label: "Card (on your card machine)" }, { value: "other", label: "Other" }, { value: "customer_account", label: payFor?.customer_id ? "Customer account (pay later)" : "Customer account (needs customer phone on the order)", disabled: !payFor?.customer_id }]} /></Form.Item>
            <Space wrap style={{ marginBottom: 12 }}>
              <Button size="small" onClick={() => form.setFieldValue("amount", outstanding)}>Exact {outstanding.toFixed(2)}</Button>
              {[300, 500, 1000].filter((n) => n < outstanding).map((n) => <Button key={n} size="small" onClick={() => form.setFieldValue("amount", n)}>{n}</Button>)}
            </Space>
            {(bill.data?.payments.length ?? 0) > 0 && <Typography.Paragraph type="secondary">Already received: {bill.data!.payments.map((p) => `${p.method.replace("_external", "")} ${Number(p.amount).toFixed(2)}`).join(" · ")}</Typography.Paragraph>}
            <Form.Item name="amount" label="Amount" rules={[{ required: true }]}><InputNumber min={0.01} max={outstanding} precision={2} style={{ width: "100%" }} /></Form.Item>
            <Form.Item name="reference" label="Reference (UPI ref / card slip no.)"><Input maxLength={128} /></Form.Item>
            <Typography.Text type="secondary">We record the payment; we do not process UPI or card payments ourselves.</Typography.Text>
          </Form>)}
      </Modal>
      <Modal open={!!freeFor} title={`Complimentary / non-chargeable · ${freeFor?.order_number ?? ""}`} okText="Apply" onCancel={() => setFreeFor(null)} onOk={() => complimentary.mutate()}
        okButtonProps={{ disabled: freeIds.length > 0 && !freeReason.trim() }} confirmLoading={complimentary.isPending} destroyOnClose>
        <Typography.Paragraph type="secondary">Ticked items are free on the bill. Tick everything for a non-chargeable bill.</Typography.Paragraph>
        <Space direction="vertical">
          {(freeFor?.items ?? []).filter((i) => i.status === "active").map((i) => (
            <label key={i.id}><input type="checkbox" checked={freeIds.includes(i.id)} onChange={(e) => setFreeIds(e.target.checked ? [...freeIds, i.id] : freeIds.filter((x) => x !== i.id))} /> {i.name} × {i.quantity}</label>))}
        </Space>
        <Input style={{ marginTop: 12 }} placeholder="Reason (required) e.g. owner's guest, service recovery" maxLength={200} value={freeReason} onChange={(e) => setFreeReason(e.target.value)} />
      </Modal>
      <Modal open={!!voiding} title={`Void ${voiding?.order_number ?? ""}`} okText="Void order" okButtonProps={{ danger: true, disabled: !voidReason.trim() }} confirmLoading={voidOrder.isPending}
        onCancel={() => setVoiding(null)} onOk={() => voidOrder.mutate()} destroyOnClose>
        <Typography.Paragraph type="secondary">Cancels the whole order and frees the table. Not possible once any payment (including advance) is recorded. Managers only.</Typography.Paragraph>
        <Input placeholder="Reason (required)" maxLength={200} value={voidReason} onChange={(e) => setVoidReason(e.target.value)} />
      </Modal>
      <Modal open={!!addFor} title={`Add items · ${addFor?.order_number ?? ""}`} okText="Send new KOT" onCancel={() => setAddFor(null)} onOk={() => add.mutate()}
        okButtonProps={{ disabled: !lines.some((l) => l.menu_item_id) }} confirmLoading={add.isPending} destroyOnClose>
        <Space direction="vertical" style={{ width: "100%" }}>
          {lines.map((l, idx) => (
            <Space key={idx} wrap>
              <Select showSearch optionFilterProp="label" placeholder="Menu item" style={{ width: 200 }} value={l.menu_item_id} loading={menu.isLoading}
                options={(menu.data ?? []).filter((m) => m.active).map((m) => ({ value: m.id, label: `${m.name} · ${m.price}` }))}
                onChange={(v) => setLines(lines.map((x, i) => (i === idx ? { ...x, menu_item_id: v, variant_id: menu.data?.find((m) => m.id === v)?.variants[0]?.id, addon_ids: [] } : x)))} />
              {(() => { const mi = menu.data?.find((m) => m.id === l.menu_item_id); return mi && (<>
                {mi.variants.length > 0 && <Select style={{ width: 150 }} value={l.variant_id} options={mi.variants.map((v) => ({ value: v.id, label: `${v.name} · ${v.price}` }))}
                  onChange={(v) => setLines(lines.map((x, i) => (i === idx ? { ...x, variant_id: v } : x)))} />}
                {mi.addons.length > 0 && <Select mode="multiple" placeholder="Add-ons" style={{ minWidth: 150 }} value={l.addon_ids} options={mi.addons.map((a) => ({ value: a.id, label: `${a.name} · +${a.price}` }))}
                  onChange={(v) => setLines(lines.map((x, i) => (i === idx ? { ...x, addon_ids: v } : x)))} />}
              </>); })()}
              <InputNumber min={1} max={100} value={l.quantity} onChange={(v) => setLines(lines.map((x, i) => (i === idx ? { ...x, quantity: v ?? 1 } : x)))} />
              <Input placeholder="Note (less spicy…)" maxLength={300} style={{ width: 170 }} value={l.notes}
                onChange={(e) => setLines(lines.map((x, i) => (i === idx ? { ...x, notes: e.target.value } : x)))} />
              {lines.length > 1 && <Button danger onClick={() => setLines(lines.filter((_, i) => i !== idx))}>×</Button>}
            </Space>))}
          <Button onClick={() => setLines([...lines, { quantity: 1 }])}>+ Another item</Button>
        </Space>
      </Modal>
      <Modal open={!!chargeFor} title={`Discount, service charge & tip · ${chargeFor?.order_number ?? ""}`} okText="Apply" onCancel={() => setChargeFor(null)} onOk={() => chargeForm.submit()} confirmLoading={charges.isPending} destroyOnClose>
        <Form form={chargeForm} layout="vertical" key={chargeFor?.id} onFinish={(v) => charges.mutate(v)}
          initialValues={{ type: chargeFor?.discount_type ?? "none", value: Number(chargeFor?.discount_value ?? 0), reason: chargeFor?.discount_reason ?? "", waive: chargeFor?.service_charge_waived ?? false, tip: Number(chargeFor?.tip ?? 0) }}>
          <Form.Item name="type" label="Discount"><Select options={[{ value: "none", label: "No discount" }, { value: "percent", label: "Percent (%)" }, { value: "fixed", label: `Fixed amount (${currency})` }]} /></Form.Item>
          <Form.Item noStyle shouldUpdate={(a, b) => a.type !== b.type}>{({ getFieldValue }) => getFieldValue("type") !== "none" && (<>
            <Form.Item name="value" label="Discount value" rules={[{ required: true }]}><InputNumber min={0.01} max={getFieldValue("type") === "percent" ? 100 : undefined} precision={2} style={{ width: "100%" }} /></Form.Item>
            <Form.Item name="reason" label="Reason (required)" rules={[{ required: true, min: 3, message: "Enter a reason" }]}><Input maxLength={300} placeholder="Regular guest, complaint, staff meal…" /></Form.Item></>)}</Form.Item>
          <Form.Item name="waive" label="Waive service charge" valuePropName="checked"><Switch /></Form.Item>
          <Form.Item name="tip" label={`Tip (${currency}) — not taxed, added to the amount payable`}><InputNumber min={0} precision={2} style={{ width: "100%" }} /></Form.Item>
        </Form>
      </Modal>
      <Modal open={!!cancelling} title={`Cancel ${cancelling?.item.name ?? "item"}?`} okText="Cancel item" okButtonProps={{ danger: true, disabled: cancelReason.trim().length < 3 }}
        onCancel={() => setCancelling(null)} onOk={() => cancel.mutate()} confirmLoading={cancel.isPending} destroyOnClose>
        <Input placeholder="Reason (required)" maxLength={300} value={cancelReason} onChange={(e) => setCancelReason(e.target.value)} />
        <Typography.Text type="secondary">Only owner, manager or cashier can cancel. The bill total is recalculated.</Typography.Text>
      </Modal>
      <BillModal orderId={billId} currency={currency} onClose={() => setBillId(null)} />
    </div>
  );
}

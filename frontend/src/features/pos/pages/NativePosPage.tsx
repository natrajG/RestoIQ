import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getAutoKot, printKot, printQueuedKot, setAutoKot } from "../printing";
import { Alert, Button, Card, Col, Empty, Input, InputNumber, Row, Segmented, Select, Skeleton, Space, Switch, Tag, Typography, message } from "antd";
import { MinusOutlined, PlusOutlined, ShoppingCartOutlined } from "@ant-design/icons";
import type { Outlet } from "../api";
import { lineLabel, lineUnitPrice, orderApi, posApi, type MenuItem } from "../api";
import { OptionPicker } from "../components/OptionPicker";
import { enqueueOrder, isNetworkError } from "../../../shared/offlineQueue";
import { computeOffline, type OfflineLine } from "../../../shared/offlineBill";
import { BillModal } from "../components/BillModal";

const QUICK_NOTES = ["Less spicy", "Extra spicy", "No onion", "No garlic", "Less oil", "Pack separately", "Serve fast"];

interface Props {
  outletId: number;
  outlet: Outlet;
}

export function NativePosPage({ outletId, outlet }: Props) {
  const [tableId, setTableId] = useState<number>();
  const [billId, setBillId] = useState<number | null>(null);
  const [cart, setCart] = useState<Record<number, number>>({});
  const [custom, setCustom] = useState<{ key: string; item: MenuItem; variantId?: number; addonIds: number[]; qty: number }[]>([]);
  const [orderType, setOrderType] = useState<"dine_in" | "takeaway" | "delivery">("dine_in");
  const [contact, setContact] = useState({ name: "", phone: "", address: "" });
  const [details, setDetails] = useState<{ covers: number | null; remark: string }>({ covers: null, remark: "" });
  const [advance, setAdvance] = useState<{ when: string; amount: number | null; method: string }>({ when: "", amount: null, method: "cash" });
  const [search, setSearch] = useState("");
  const [picking, setPicking] = useState<MenuItem | null>(null);
  const client = useQueryClient();
  const menu = useQuery({ queryKey: ["menu", outletId], queryFn: () => posApi.menu(outletId) });
  const tables = useQuery({ queryKey: ["tables", outletId], queryFn: () => posApi.tables(outletId) });
  const availableTables = (tables.data ?? []).filter((table) => ["FREE", "READY"].includes(table.status));
  const selectedItems = useMemo(
    () => (menu.data ?? []).filter((item) => item.active && cart[item.id]),
    [cart, menu.data],
  );
  const subtotalEstimate = selectedItems.reduce((total, item) => total + Number(item.price) * cart[item.id], 0)
    + custom.reduce((total, c) => total + lineUnitPrice(c.item, c.variantId, c.addonIds) * c.qty, 0);
  const order = useMutation({
    mutationFn: async (selectedTableId: number | undefined) => {
      const key = crypto.randomUUID();
      const body = {
      restaurant_id: outletId,
      table_id: orderType === "dine_in" ? selectedTableId : undefined,
      order_type: orderType,
      contact_name: contact.name.trim() || undefined,
      contact_phone: contact.phone.trim() || undefined,
      scheduled_for: orderType !== "dine_in" && advance.when ? new Date(advance.when).toISOString() : undefined,
      advance_amount: orderType !== "dine_in" && advance.amount ? advance.amount : undefined,
      advance_method: orderType !== "dine_in" && advance.amount ? advance.method : undefined,
      covers: details.covers ?? undefined,
      remark: details.remark.trim() || undefined,
      delivery_address: orderType === "delivery" ? contact.address.trim() : undefined,
      items: [
        ...selectedItems.map((item) => ({ menu_item_id: item.id, quantity: cart[item.id] })),
        ...custom.map((c) => ({ menu_item_id: c.item.id, quantity: c.qty, variant_id: c.variantId, addon_ids: c.addonIds })),
      ],
      };
      try {
        return await posApi.createOrder(outletId, body, key);
      } catch (e) {
        if (!isNetworkError(e)) throw e;
        // The request may or may not have reached the server; the same key makes the retry safe.
        const cfg = (outlet as Outlet & { tax_config?: { gst_scheme?: string; service_charge_pct?: string; round_off?: boolean } }).tax_config ?? {};
        const lines: OfflineLine[] = [
          ...selectedItems.map((i) => ({ name: i.name, qty: cart[i.id], unitPaise: Math.round(Number(i.price) * 100), rate: Number(i.tax_rate) })),
          ...custom.map((c) => ({ name: lineLabel(c.item, c.variantId, c.addonIds), qty: c.qty, unitPaise: Math.round(lineUnitPrice(c.item, c.variantId, c.addonIds) * 100), rate: Number(c.item.tax_rate) })),
        ];
        const extra = {
          restaurant: outlet.name, orderType, contact: [contact.name, contact.phone].filter(Boolean).join(" "), lines,
          tableName: (tables.data ?? []).find((t) => t.id === selectedTableId)?.name,
          charges: computeOffline(lines, Number(cfg.service_charge_pct ?? 0), cfg.gst_scheme === "composition", !!cfg.round_off),
        };
        const printNow = getAutoKot();
        const takenAt = new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
        const remark = [`Taken offline at ${takenAt}`, body.remark].filter(Boolean).join(" · ").slice(0, 300);
        enqueueOrder(outletId, { ...body, remark, discount_amount: "0" }, `${orderType.replace("_", "-")} order, ${lines.length} line(s)`, key, { ...extra, kotPrinted: printNow });
        if (printNow) printQueuedKot({ ...extra, key, outletId, body, label: "", createdAt: new Date().toISOString() });
        return null;
      }
    },
    onSuccess: async (created) => {
      setCart({});
      setCustom([]);
      setContact({ name: "", phone: "", address: "" });
      setTableId(undefined);
      setDetails({ covers: null, remark: "" });
      setAdvance({ when: "", amount: null, method: "cash" });
      if (!created) {
        message.warning("Offline: order saved on this device. It reaches the kitchen when the internet is back.");
        return;
      }
      await Promise.all([
        client.invalidateQueries({ queryKey: ["tables", outletId] }),
        client.invalidateQueries({ queryKey: ["kitchen", outletId] }),
        client.invalidateQueries({ queryKey: ["orders", outletId] }),
      ]);
      message.success(`Order ${created.order_number} sent to the kitchen`);
      if (getAutoKot()) {
        try {
          const full = await orderApi.get(created.id);
          printKot(full, 1, (tables.data ?? []).find((t) => t.id === full.table_id)?.name ?? null, outlet.name);
        } catch { /* printing is best effort; the order is already sent */ }
      }
      setBillId(created.id);
    },
    onError: (error: Error) => message.error(error.message),
  });

  return (
    <div className="page">
      <div className="page-heading">
        <div><Typography.Title level={2}>Native POS</Typography.Title><Typography.Paragraph type="secondary">Create a dine-in order and send it to the kitchen.</Typography.Paragraph></div>
        <Space><Typography.Text type="secondary">Auto-print KOT</Typography.Text><Switch defaultChecked={getAutoKot()} onChange={setAutoKot} /><Tag color="blue">OUR POS · {outlet.currency}</Tag></Space>
      </div>
      {(menu.error || tables.error) && <Alert type="error" showIcon message="Menu or table data could not be loaded" />}
      {menu.isLoading || tables.isLoading ? <Skeleton active /> : (
        <Row gutter={[18, 18]}>
          <Col xs={24} xl={16}>
            <Input.Search allowClear autoFocus placeholder="Search item name or short code" value={search} onChange={(e) => setSearch(e.target.value)} style={{ marginBottom: 14 }}
              onSearch={(v) => { const hits = (menu.data ?? []).filter((i) => i.active && i.sku.toLowerCase() === v.trim().toLowerCase()); if (hits.length === 1) { const i = hits[0]; if (i.variants.length || i.addons.length) setPicking(i); else setCart((c) => ({ ...c, [i.id]: (c[i.id] ?? 0) + 1 })); setSearch(""); } }} />
            {menu.data?.length ? (
              <div className="menu-grid">
                {menu.data.filter((item) => item.active && (`${item.name} ${item.sku}`).toLowerCase().includes(search.trim().toLowerCase())).map((item) => (
                  <Card className="menu-card" key={item.id}>
                    <div className="menu-card-title"><b>{item.name}</b><Tag>{item.sku}</Tag></div>
                    <div className="menu-card-bottom">
                      <Typography.Text strong>{item.variants.length ? "from " : ""}{outlet.currency} {Number(item.variants.length ? Math.min(...item.variants.map((v) => Number(v.price))) : item.price).toFixed(2)}</Typography.Text>
                      {item.variants.length || item.addons.length ? (
                        <Button type="primary" icon={<PlusOutlined />} onClick={() => setPicking(item)}>Choose</Button>
                      ) : (
                      <Space>
                        <Button
                          aria-label={`Decrease ${item.name}`}
                          icon={<MinusOutlined />}
                          disabled={!cart[item.id]}
                          onClick={() => setCart((current) => {
                            const next = { ...current, [item.id]: (current[item.id] ?? 0) - 1 };
                            if (next[item.id] <= 0) delete next[item.id];
                            return next;
                          })}
                        />
                        <InputNumber aria-label={`${item.name} quantity`} min={0} max={100} value={cart[item.id] ?? 0} onChange={(value) => setCart((current) => ({ ...current, [item.id]: Number(value ?? 0) }))} />
                        <Button aria-label={`Add ${item.name}`} type="primary" icon={<PlusOutlined />} onClick={() => setCart((current) => ({ ...current, [item.id]: (current[item.id] ?? 0) + 1 }))} />
                      </Space>)}
                    </div>
                  </Card>
                ))}
              </div>
            ) : <Card><Empty description="No menu items configured for this outlet." /></Card>}
          </Col>
          <Col xs={24} xl={8}>
            <Card className="cart-card" title={<Space><ShoppingCartOutlined />Current order</Space>}>
              <Segmented block value={orderType} onChange={(v) => setOrderType(v as typeof orderType)} style={{ marginBottom: 12 }}
                options={[{ value: "dine_in", label: "Dine-in" }, { value: "takeaway", label: "Takeaway" }, { value: "delivery", label: "Delivery" }]} />
              {orderType !== "dine_in" && (
                <Space direction="vertical" style={{ width: "100%", marginBottom: 14 }} size={8}>
                  <Input placeholder="Customer name (optional)" maxLength={120} value={contact.name} onChange={(e) => setContact({ ...contact, name: e.target.value })} />
                  <Input placeholder={orderType === "delivery" ? "Phone (required)" : "Phone (optional)"} maxLength={20} value={contact.phone} onChange={(e) => setContact({ ...contact, phone: e.target.value })} />
                  <Input type="datetime-local" aria-label="Pickup or delivery time" title="Optional: schedule this order for later" value={advance.when} onChange={(e) => setAdvance({ ...advance, when: e.target.value })} />
                  {advance.when && <Space.Compact style={{ width: "100%" }}>
                    <InputNumber min={0} placeholder="Advance received" style={{ width: "60%" }} value={advance.amount} onChange={(v) => setAdvance({ ...advance, amount: v ? Number(v) : null })} />
                    <Select style={{ width: "40%" }} value={advance.method} onChange={(method) => setAdvance({ ...advance, method })} options={[{ value: "cash", label: "Cash" }, { value: "upi_external", label: "UPI" }, { value: "card_external", label: "Card" }]} />
                  </Space.Compact>}
                  {orderType === "delivery" && <Input.TextArea rows={2} placeholder="Delivery address (required)" maxLength={400} value={contact.address} onChange={(e) => setContact({ ...contact, address: e.target.value })} />}
                </Space>)}
              {orderType === "dine_in" && <Select
                placeholder="Select an available table"
                value={tableId}
                onChange={setTableId}
                showSearch optionFilterProp="label"
                options={availableTables.map((table) => ({ value: table.id, label: `${table.name} · ${table.seats} seats` }))}
                style={{ width: "100%", marginBottom: 18 }}
              />}
              <Space direction="vertical" style={{ width: "100%", marginBottom: 14 }} size={6}>
                {orderType === "dine_in" && <InputNumber min={1} max={500} placeholder="Covers (guests)" style={{ width: "100%" }} value={details.covers} onChange={(v) => setDetails({ ...details, covers: v ? Number(v) : null })} />}
                <Input.TextArea rows={1} maxLength={300} placeholder="Order note for kitchen (optional)" value={details.remark} onChange={(e) => setDetails({ ...details, remark: e.target.value })} />
                <Space size={[4, 4]} wrap>
                  {QUICK_NOTES.map((n) => <Tag.CheckableTag key={n} checked={details.remark.includes(n)} onChange={(on) => setDetails((d) => ({ ...d, remark: on ? [d.remark.trim(), n].filter(Boolean).join(", ") : d.remark.split(",").map((x) => x.trim()).filter((x) => x && x !== n).join(", ") }))}>{n}</Tag.CheckableTag>)}
                </Space>
              </Space>
              {selectedItems.map((item) => (
                <div className="cart-row" key={item.id}><span>{item.name} × {cart[item.id]}</span><b>{outlet.currency} {(Number(item.price) * cart[item.id]).toFixed(2)}</b></div>
              ))}
              {custom.map((c) => (
                <div className="cart-row" key={c.key}><span>{lineLabel(c.item, c.variantId, c.addonIds)} × {c.qty}</span><b>{outlet.currency} {(lineUnitPrice(c.item, c.variantId, c.addonIds) * c.qty).toFixed(2)} <Button size="small" type="link" danger onClick={() => setCustom((l) => l.filter((x) => x.key !== c.key))}>×</Button></b></div>
              ))}
              {!selectedItems.length && !custom.length && <div className="empty-note">Add menu items to start an order.</div>}
              <div className="cart-total"><span>Subtotal estimate</span><b>{outlet.currency} {subtotalEstimate.toFixed(2)}</b></div>
              <Typography.Paragraph type="secondary" className="cart-note">Taxes are calculated by the server using configured item tax rates.</Typography.Paragraph>
              <Button
                type="primary"
                block
                size="large"
                disabled={(!selectedItems.length && !custom.length) || (orderType === "dine_in" && !tableId) || (orderType === "delivery" && (!contact.phone.trim() || !contact.address.trim()))}
                loading={order.isPending}
                onClick={() => order.mutate(tableId)}
              >
                Send to kitchen
              </Button>
            </Card>
          </Col>
        </Row>
      )}
      <OptionPicker item={picking} currency={outlet.currency} onCancel={() => setPicking(null)}
        onPick={(p) => { if (picking) setCustom((l) => [...l, { key: crypto.randomUUID(), item: picking, variantId: p.variantId, addonIds: p.addonIds, qty: 1 }]); setPicking(null); }} />
      <BillModal orderId={billId} currency={outlet.currency} onClose={() => setBillId(null)} />
    </div>
  );
}

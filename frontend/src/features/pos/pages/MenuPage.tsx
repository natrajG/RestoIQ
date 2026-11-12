import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Switch, Table, Tag, Typography, message } from "antd";
import { useState } from "react";
import { MenuImport } from "../components/MenuImport";
import { menuApi, posApi, type MenuItem, type MenuOption } from "../api";

const GST = [0, 5, 12, 18, 28].map((v) => ({ value: String(v), label: `${v}%` }));

export function MenuPage({ outletId, currency }: { outletId: number; currency: string }) {
  const client = useQueryClient();
  const [form] = Form.useForm();
  const [catName, setCatName] = useState("");
  const menu = useQuery({ queryKey: ["menu", outletId], queryFn: () => posApi.menu(outletId) });
  const cats = useQuery({ queryKey: ["menu-cats", outletId], queryFn: () => menuApi.categories(outletId) });
  const gst = useQuery({ queryKey: ["gst", outletId], queryFn: () => menuApi.gst(outletId) });
  const refresh = () => { void client.invalidateQueries({ queryKey: ["menu", outletId] }); void client.invalidateQueries({ queryKey: ["menu-cats", outletId] }); };
  const onError = (e: Error) => message.error(e.message);
  const addCat = useMutation({ mutationFn: () => menuApi.addCategory(outletId, catName), onSuccess: () => { setCatName(""); refresh(); }, onError });
  const [optFor, setOptFor] = useState<MenuItem | null>(null);
  const [optForm] = Form.useForm();
  const addOpt = useMutation({
    mutationFn: (v: { kind: "variant" | "addon"; name: string; price: number }) => menuApi.addOption(outletId, optFor!.id, { kind: v.kind, name: v.name.trim(), price: v.price.toFixed(2) }),
    onSuccess: () => { optForm.resetFields(); refresh(); }, onError });
  const delOpt = useMutation({ mutationFn: (id: number) => menuApi.removeOption(outletId, optFor!.id, id), onSuccess: refresh, onError });
  const current = menu.data?.find((m) => m.id === optFor?.id) ?? optFor;
  const optList = (title: string, list: MenuOption[] | undefined) => !!list?.length && (
    <div style={{ marginBottom: 8 }}><b>{title}</b>{list.map((o) => (
      <div key={o.id} style={{ display: "flex", justifyContent: "space-between" }}><span>{o.name} · {currency} {Number(o.price).toFixed(2)}</span>
        <Popconfirm title="Remove?" onConfirm={() => delOpt.mutate(o.id)}><Button size="small" type="link" danger>Remove</Button></Popconfirm></div>))}</div>);
  const delCat = useMutation({ mutationFn: (id: number) => menuApi.deleteCategory(outletId, id), onSuccess: refresh, onError });
  const addItem = useMutation({
    mutationFn: (v: { name: string; sku: string; price: number; tax_rate: string; category_id?: number }) =>
      menuApi.addItem(outletId, { name: v.name, sku: v.sku, price: v.price.toFixed(2), tax_rate: v.tax_rate, category_id: v.category_id ?? null }),
    onSuccess: () => { form.resetFields(); form.setFieldValue("tax_rate", "5"); message.success("Item added"); refresh(); }, onError,
  });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Parameters<typeof menuApi.updateItem>[2] }) => menuApi.updateItem(outletId, id, body),
    onSuccess: refresh, onError,
  });
  const delItem = useMutation({ mutationFn: (id: number) => menuApi.deleteItem(outletId, id), onSuccess: () => { message.success("Item deleted"); refresh(); }, onError });
  const scheme = useMutation({ mutationFn: menuApi.setGst.bind(null, outletId), onSuccess: () => { void client.invalidateQueries({ queryKey: ["gst", outletId] }); message.success("GST setting saved. It applies to new orders."); }, onError });
  const billing = useQuery({ queryKey: ["billing", outletId], queryFn: () => menuApi.billing(outletId) });
  const saveBilling = useMutation({
    mutationFn: (body: { service_charge_pct: number; round_off: boolean; upi_id?: string }) => menuApi.setBilling(outletId, body),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ["billing", outletId] }); message.success("Billing settings saved. They apply to bills created or changed from now on."); }, onError,
  });
  const composition = gst.data?.gst_scheme === "composition";

  return (
    <div className="page">
      <div className="page-heading"><div>
        <Typography.Title level={2}>Menu, prices & GST</Typography.Title>
        <Typography.Paragraph type="secondary">Prices are entered excluding GST; GST is added on the bill and split into CGST and SGST. Changes apply to new orders only.</Typography.Paragraph>
      </div></div>
      <Card className="section-card" title="GST scheme">
        <Space direction="vertical">
          <Select style={{ width: 360 }} value={gst.data?.gst_scheme} loading={gst.isLoading} onChange={(v) => scheme.mutate(v)}
            options={[{ value: "regular", label: "Regular — charge GST on bills" }, { value: "composition", label: "Composition scheme — no GST on bills" }]} />
          <Typography.Text type="secondary">Standalone restaurants currently charge 5% GST without input tax credit; restaurants in hotels with room tariff of ₹7,500 or more charge 18%. Confirm your rate and scheme with your accountant. Composition dealers cannot show GST on bills.</Typography.Text>
          {composition && <Alert type="warning" showIcon message="Composition: new orders are billed with 0% tax and the bill carries the composition notice." />}
          {!composition && <Typography.Text type="secondary">Bills show your GSTIN only if you entered one at signup.</Typography.Text>}
        </Space>
      </Card>
      <Card className="section-card" title="Service charge & round-off" loading={billing.isLoading}>
        {billing.data && (
          <Space wrap align="center">
            <span>Service charge %</span>
            <InputNumber min={0} max={20} step={0.5} precision={2} defaultValue={Number(billing.data.service_charge_pct)} key={billing.data.service_charge_pct}
              onBlur={(e) => { const v = Number(e.target.value); if (!Number.isNaN(v) && v !== Number(billing.data!.service_charge_pct)) saveBilling.mutate({ service_charge_pct: v, round_off: billing.data!.round_off }); }} />
            <span>Round bill to nearest rupee</span>
            <Switch checked={billing.data.round_off} onChange={(v) => saveBilling.mutate({ service_charge_pct: Number(billing.data!.service_charge_pct), round_off: v })} />
            <Typography.Text type="secondary">Service charge is taxed at the GST rate of the items, and a cashier can waive it per bill. Customers may refuse it, so confirm your policy with your accountant. Tips are separate and not taxed.</Typography.Text>
          </Space>)}
      </Card>
      <Card className="section-card" title="UPI QR on bills" loading={billing.isLoading}>
        {billing.data && (
          <Space wrap align="center">
            <Input style={{ width: 280 }} placeholder="yourshop@bank" defaultValue={billing.data.upi_id} key={billing.data.upi_id} maxLength={80}
              onBlur={(e) => { const v = e.target.value.trim(); if (v !== billing.data!.upi_id) saveBilling.mutate({ service_charge_pct: Number(billing.data!.service_charge_pct), round_off: billing.data!.round_off, upi_id: v }); }} />
            <Typography.Text type="secondary">The restaurant's own UPI ID. Printed bills with an amount still due show a QR for exactly that amount; the money goes straight to this account. Record the payment in RestoIQ after the customer pays. Leave blank to hide the QR.</Typography.Text>
          </Space>)}
      </Card>
      <Card className="section-card" title="Categories">
        <Space wrap>
          {(cats.data ?? []).map((c) => (
            <Popconfirm key={c.id} title="Delete category?" description="Its items stay on the menu without a category." onConfirm={() => delCat.mutate(c.id)}>
              <Tag closable onClose={(e) => e.preventDefault()}>{c.name}</Tag>
            </Popconfirm>
          ))}
          <Input placeholder="New category" value={catName} maxLength={120} onChange={(e) => setCatName(e.target.value)} onPressEnter={() => catName.trim() && addCat.mutate()} style={{ width: 200 }} />
          <Button onClick={() => addCat.mutate()} disabled={!catName.trim()} loading={addCat.isPending}>Add</Button>
        </Space>
      </Card>
      <MenuImport outletId={outletId} onDone={refresh} />
      <Card className="section-card" title="Add item">
        <Form form={form} layout="inline" initialValues={{ tax_rate: "5" }} onFinish={(v) => addItem.mutate(v)} style={{ rowGap: 12 }}>
          <Form.Item name="name" rules={[{ required: true }]}><Input placeholder="Item name" maxLength={120} /></Form.Item>
          <Form.Item name="sku" rules={[{ required: true }]}><Input placeholder="Code / SKU" maxLength={64} style={{ width: 120 }} /></Form.Item>
          <Form.Item name="price" rules={[{ required: true }]}><InputNumber placeholder={`Price (${currency})`} min={0} precision={2} style={{ width: 140 }} /></Form.Item>
          <Form.Item name="tax_rate"><Select options={GST} style={{ width: 90 }} /></Form.Item>
          <Form.Item name="category_id"><Select allowClear placeholder="Category" style={{ width: 160 }} options={(cats.data ?? []).map((c) => ({ value: c.id, label: c.name }))} /></Form.Item>
          <Button type="primary" htmlType="submit" loading={addItem.isPending}>Add item</Button>
        </Form>
      </Card>
      <Card className="section-card" title="Items">
        <Table<MenuItem> size="small" rowKey="id" loading={menu.isLoading} dataSource={menu.data ?? []} pagination={{ pageSize: 20, hideOnSinglePage: true }}
          columns={[
            { title: "Item", dataIndex: "name", render: (v: string, row) => (
              <Input size="small" key={`${row.id}-${v}`} defaultValue={v} maxLength={120} style={{ minWidth: 160 }}
                onBlur={(e) => { const n = e.target.value.trim(); if (n && n !== v) update.mutate({ id: row.id, body: { name: n } }); else e.target.value = v; }} />) },
            { title: "Category", dataIndex: "category_id", render: (id: number | null, row) => (
              <Select size="small" allowClear style={{ width: 140 }} value={id ?? undefined} placeholder="None"
                options={(cats.data ?? []).map((c) => ({ value: c.id, label: c.name }))}
                onChange={(v) => update.mutate({ id: row.id, body: { category_id: v ?? null } })} />) },
            { title: `Price (${currency})`, dataIndex: "price", render: (v: string, row) => (
              <InputNumber size="small" min={0} precision={2} defaultValue={Number(v)} style={{ width: 100 }}
                onBlur={(e) => { const n = Number(e.target.value); if (!Number.isNaN(n) && n !== Number(v)) update.mutate({ id: row.id, body: { price: n.toFixed(2) } }); }} />) },
            { title: "GST", dataIndex: "tax_rate", render: (v: string, row) => (
              <Select size="small" style={{ width: 80 }} value={String(Number(v))} options={GST} disabled={composition}
                onChange={(t) => update.mutate({ id: row.id, body: { tax_rate: t } })} />) },
            { title: "Customer pays", render: (_, row) => `${(Number(row.price) * (1 + (composition ? 0 : Number(row.tax_rate)) / 100)).toFixed(2)}` },
            { title: "Options", render: (_, row) => <Button size="small" onClick={() => setOptFor(row)}>Sizes & add-ons{row.variants.length + row.addons.length ? ` (${row.variants.length + row.addons.length})` : ""}</Button> },
            { title: "", render: (_, row) => (
              <Popconfirm title="Delete this item?" description="Only items never sold can be deleted; otherwise switch it off." onConfirm={() => delItem.mutate(row.id)}>
                <Button size="small" type="link" danger>Delete</Button></Popconfirm>) },
            { title: "Available", dataIndex: "active", render: (a: boolean, row) => <Switch size="small" checked={a} onChange={(v) => update.mutate({ id: row.id, body: { active: v } })} /> },
          ]} />
      </Card>
      <Modal open={!!optFor} title={`Sizes & add-ons · ${optFor?.name ?? ""}`} footer={null} onCancel={() => setOptFor(null)} destroyOnClose>
        {optList("Sizes / variants (price replaces the item price)", current?.variants)}
        {optList("Add-ons (price added on top)", current?.addons)}
        <Form form={optForm} layout="inline" initialValues={{ kind: "variant" }} onFinish={(v) => addOpt.mutate(v)} style={{ rowGap: 8 }}>
          <Form.Item name="kind"><Select style={{ width: 110 }} options={[{ value: "variant", label: "Size" }, { value: "addon", label: "Add-on" }]} /></Form.Item>
          <Form.Item name="name" rules={[{ required: true }]}><Input placeholder="Half, Extra cheese…" maxLength={80} /></Form.Item>
          <Form.Item name="price" rules={[{ required: true }]}><InputNumber min={0} precision={2} placeholder="Price" style={{ width: 100 }} /></Form.Item>
          <Button type="primary" htmlType="submit" loading={addOpt.isPending}>Add</Button>
        </Form>
      </Modal>
    </div>
  );
}

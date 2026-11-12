import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Form, Input, Modal, Select, Space, Table, Tag, Typography, message } from "antd";
import { api } from "../../../shared/api/client";

interface Channel { id: number; provider: string; label: string | null; active: boolean; created_at: string; webhook_url?: string; secret?: string }
interface DeliveryOrder {
  id: number; provider: string; external_id: string; status: string; order_id: number | null; order_number: string | null;
  aggregator_total: string | null; commission: string; total_mismatch: boolean; unmatched: string[] | null; created_at: string;
}
interface Summary { needs_mapping: number; channels: { provider: string; orders: number; gross: string; commission: string; net: string }[] }
interface MenuOpt { id: number; name: string; active: boolean }

const colors: Record<string, string> = { created: "green", needs_mapping: "orange", cancelled: "red" };

export function DeliveryPage({ outletId }: { outletId: number }) {
  const client = useQueryClient();
  const base = `/outlets/${outletId}/delivery`;
  const channels = useQuery({ queryKey: ["dl-ch", outletId], queryFn: () => api<Channel[]>(`${base}/channels`) });
  const orders = useQuery({ queryKey: ["dl-or", outletId], queryFn: () => api<DeliveryOrder[]>(`${base}/orders`), refetchInterval: 15000 });
  const summary = useQuery({ queryKey: ["dl-su", outletId], queryFn: () => api<Summary>(`${base}/summary`), refetchInterval: 15000 });
  const menu = useQuery({ queryKey: ["dl-menu", outletId], queryFn: () => api<MenuOpt[]>(`/outlets/${outletId}/menu`) });
  const [created, setCreated] = useState<Channel | null>(null);
  const [resolving, setResolving] = useState<DeliveryOrder | null>(null);
  const [form] = Form.useForm();
  const [mapForm] = Form.useForm();
  const refresh = () => { void client.invalidateQueries({ queryKey: ["dl-ch", outletId] }); void client.invalidateQueries({ queryKey: ["dl-or", outletId] }); void client.invalidateQueries({ queryKey: ["dl-su", outletId] }); };

  const create = useMutation({
    mutationFn: (v: { provider: string; label?: string }) => api<Channel>(`${base}/channels`, { method: "POST", body: JSON.stringify(v) }),
    onSuccess: (c) => { setCreated(c); form.resetFields(); refresh(); },
    onError: (e: Error) => message.error(e.message),
  });
  const disable = useMutation({
    mutationFn: (id: number) => api(`${base}/channels/${id}/disable`, { method: "POST" }),
    onSuccess: refresh, onError: (e: Error) => message.error(e.message),
  });
  const resolve = useMutation({
    mutationFn: (v: { id: number; mappings: Record<string, number> }) => api(`${base}/orders/${v.id}/resolve`, { method: "POST", body: JSON.stringify({ mappings: v.mappings }) }),
    onSuccess: () => { message.success("Order created and sent to kitchen"); setResolving(null); refresh(); },
    onError: (e: Error) => message.error(e.message),
  });

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Typography.Title level={3} style={{ margin: 0 }}>Delivery apps</Typography.Title>
      <Alert type="info" showIcon message="Orders arrive through an aggregator or middleware (for example UrbanPiper) that posts to the webhook URL below. Swiggy and Zomato do not offer a public direct API." />
      {summary.data && summary.data.needs_mapping > 0 && <Alert type="warning" showIcon message={`${summary.data.needs_mapping} order(s) have items we could not match to your menu. Map them below.`} />}

      <Card title="Channel summary">
        <Table size="small" pagination={false} rowKey="provider" dataSource={summary.data?.channels ?? []}
          columns={[{ title: "Provider", dataIndex: "provider" }, { title: "Orders", dataIndex: "orders" }, { title: "Gross", dataIndex: "gross" },
            { title: "Commission", dataIndex: "commission" }, { title: "Net", dataIndex: "net" }]} />
      </Card>

      <Card title="Connections">
        <Form form={form} layout="inline" onFinish={(v) => create.mutate(v)} style={{ marginBottom: 12 }}>
          <Form.Item name="provider" rules={[{ required: true }]}><Select placeholder="Provider" style={{ width: 160 }} options={["swiggy", "zomato", "urbanpiper", "other"].map((p) => ({ value: p, label: p }))} /></Form.Item>
          <Form.Item name="label"><Input placeholder="Label (optional)" /></Form.Item>
          <Button type="primary" htmlType="submit" loading={create.isPending}>Create connection</Button>
        </Form>
        <Table size="small" pagination={false} rowKey="id" dataSource={channels.data ?? []}
          columns={[{ title: "Provider", dataIndex: "provider" }, { title: "Label", dataIndex: "label" },
            { title: "Status", dataIndex: "active", render: (a: boolean) => <Tag color={a ? "green" : "default"}>{a ? "active" : "disabled"}</Tag> },
            { title: "", render: (_: unknown, c: Channel) => c.active && <Button size="small" danger onClick={() => disable.mutate(c.id)}>Disable</Button> }]} />
      </Card>

      <Card title="Incoming orders">
        <Table size="small" rowKey="id" dataSource={orders.data ?? []} pagination={{ pageSize: 10 }}
          columns={[{ title: "Time", dataIndex: "created_at", render: (t: string) => new Date(t).toLocaleString() },
            { title: "Provider", dataIndex: "provider" }, { title: "Ref", dataIndex: "external_id" },
            { title: "Order", dataIndex: "order_number" },
            { title: "Status", dataIndex: "status", render: (s: string, r: DeliveryOrder) => <Space><Tag color={colors[s]}>{s}</Tag>{r.total_mismatch && <Tag color="gold">total mismatch</Tag>}</Space> },
            { title: "Commission", dataIndex: "commission" },
            { title: "", render: (_: unknown, r: DeliveryOrder) => r.status === "needs_mapping" && <Button size="small" onClick={() => { mapForm.resetFields(); setResolving(r); }}>Map items</Button> }]} />
      </Card>

      <Modal open={!!created} title="Connection created" onCancel={() => setCreated(null)} onOk={() => setCreated(null)} cancelButtonProps={{ style: { display: "none" } }}>
        <Alert type="warning" showIcon style={{ marginBottom: 12 }} message="Copy the secret now. It is shown only once." />
        <Typography.Paragraph>Webhook URL<br /><Typography.Text code copyable>{created?.webhook_url}</Typography.Text></Typography.Paragraph>
        <Typography.Paragraph>Signing secret (HMAC-SHA256, header X-Signature)<br /><Typography.Text code copyable>{created?.secret}</Typography.Text></Typography.Paragraph>
      </Modal>

      <Modal open={!!resolving} title="Map items to your menu" onCancel={() => setResolving(null)} onOk={() => mapForm.submit()} confirmLoading={resolve.isPending}>
        <Form form={mapForm} layout="vertical" onFinish={(v: Record<string, number>) => resolving && resolve.mutate({ id: resolving.id, mappings: v })}>
          {(resolving?.unmatched ?? []).map((name) => (
            <Form.Item key={name} name={name} label={name} rules={[{ required: true }]}>
              <Select showSearch optionFilterProp="label" options={(menu.data ?? []).filter((m) => m.active).map((m) => ({ value: m.id, label: m.name }))} />
            </Form.Item>
          ))}
        </Form>
      </Modal>
    </Space>
  );
}

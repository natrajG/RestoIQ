import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Alert, Button, Card, Col, Descriptions, Empty, Form, Input, Modal, Popconfirm, Radio, Row, Select, Space, Statistic, Switch, Table, Tabs, Tag, Typography, message } from "antd";
import { api } from "../../shared/api/client";

interface Field { key: string; label: string; secret: boolean; required: boolean; help: string }
interface Provider {
  slug: string; name: string; category: string; description: string; availability: "live" | "mock" | "coming_soon";
  capabilities: string[]; planned_capabilities: string[]; requirements: string; docs_url: string | null;
  manage_path: string | null; connection_status: string; credential_fields: Field[]; connection_ids: number[]; last_sync_at: string | null;
}
interface Connection {
  id: number; provider: string; restaurant_id: number | null; status: string; config: { sync_outbound?: boolean };
  last_error: string | null; circuit_open: boolean; last_connected_at: string | null; last_sync_at: string | null;
}
interface EventRow { id: number; provider: string; event_type: string; processing_status: string; retry_count: number; error: string | null; created_at: string; payload: unknown }
interface Job { id: number; connection_id: number; operation: string; status: string; attempts: number; error_message: string | null; next_attempt_at: string }
interface Monitoring {
  connections: number; active: number; errors: { id: number; provider: string; error: string; circuit_open: boolean }[];
  jobs: Record<string, number>; events_24h: Record<string, number>; last_successful_sync: string | null;
}

const statusColor: Record<string, string> = { connected: "green", error: "red", not_connected: "default", disabled: "default", processed: "green", succeeded: "green", failed: "red", dead: "red", pending: "orange", received: "blue", running: "blue" };
const fmt = (t: string | null) => (t ? new Date(t).toLocaleString() : "never");

export function IntegrationsPage({ outletId }: { outletId: number }) {
  const client = useQueryClient();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string>("All");
  const [connecting, setConnecting] = useState<Provider | null>(null);
  const [shown, setShown] = useState<{ url: string; name: string } | null>(null);
  const [form] = Form.useForm();
  const providers = useQuery({ queryKey: ["int-providers"], queryFn: () => api<Provider[]>("/integrations/providers") });
  const connections = useQuery({ queryKey: ["int-conns"], queryFn: () => api<Connection[]>("/integrations/connections") });
  const events = useQuery({ queryKey: ["int-events"], queryFn: () => api<EventRow[]>("/integrations/events"), refetchInterval: 15000 });
  const jobs = useQuery({ queryKey: ["int-jobs"], queryFn: () => api<Job[]>("/integrations/jobs"), refetchInterval: 15000 });
  const monitor = useQuery({ queryKey: ["int-mon"], queryFn: () => api<Monitoring>("/integrations/monitoring"), refetchInterval: 15000 });
  const refresh = () => ["int-providers", "int-conns", "int-events", "int-jobs", "int-mon"].forEach((k) => void client.invalidateQueries({ queryKey: [k] }));
  const err = (e: Error) => message.error(e.message);

  const connect = useMutation({
    mutationFn: (v: { credentials: Record<string, string>; scope: "outlet" | "all" }) => api<Connection & { webhook_url: string }>("/integrations/connections", {
      method: "POST", body: JSON.stringify({ provider: connecting?.slug, restaurant_id: v.scope === "outlet" ? outletId : null, credentials: v.credentials }) }),
    onSuccess: (c) => { setShown({ url: c.webhook_url, name: connecting?.name ?? "" }); setConnecting(null); form.resetFields(); refresh(); },
    onError: err,
  });
  const act = useMutation({
    mutationFn: (a: { path: string; method?: string; body?: unknown }) => api<{ ok?: boolean; error?: string; webhook_url?: string }>(a.path, { method: a.method ?? "POST", body: a.body ? JSON.stringify(a.body) : undefined }),
    onSuccess: (r, a) => {
      if (a.path.endsWith("/test")) r.ok ? message.success("Connection OK") : message.error(r.error ?? "Test failed");
      if (r.webhook_url) setShown({ url: r.webhook_url, name: "New webhook URL" });
      refresh();
    },
    onError: err,
  });

  const categories = useMemo(() => ["All", ...Array.from(new Set((providers.data ?? []).map((p) => p.category)))], [providers.data]);
  const visible = (providers.data ?? []).filter((p) => (category === "All" || p.category === category) && p.name.toLowerCase().includes(search.toLowerCase()));
  const nameOf = (slug: string) => providers.data?.find((p) => p.slug === slug)?.name ?? slug;

  const card = (p: Provider) => {
    const soon = p.availability === "coming_soon";
    return (
      <Col xs={24} md={12} xl={8} key={p.slug}>
        <Card title={<Space>{p.name}{p.availability === "mock" && <Tag color="purple">Test only</Tag>}{soon && <Tag>Coming soon</Tag>}</Space>}
          extra={!soon && <Tag color={statusColor[p.connection_status]}>{p.connection_status.replace("_", " ")}</Tag>} style={{ height: "100%" }}>
          <Tag>{p.category}</Tag>
          <Typography.Paragraph style={{ marginTop: 8 }}>{p.description}</Typography.Paragraph>
          {p.capabilities.length > 0 && <Space wrap size={[4, 4]} style={{ marginBottom: 8 }}>{p.capabilities.map((c) => <Tag key={c} color="blue">{c.replace(/_/g, " ")}</Tag>)}</Space>}
          {p.planned_capabilities.length > 0 && <Typography.Paragraph type="secondary" style={{ fontSize: 12 }}>Planned, not available: {p.planned_capabilities.join("; ")}</Typography.Paragraph>}
          {p.requirements && <Typography.Paragraph type="secondary" style={{ fontSize: 12 }}>Needs: {p.requirements}</Typography.Paragraph>}
          {!soon && <Typography.Paragraph type="secondary" style={{ fontSize: 12 }}>Last sync: {fmt(p.last_sync_at)}</Typography.Paragraph>}
          <Space>
            {p.manage_path ? <Button type="primary" onClick={() => navigate(p.manage_path as string)}>{p.connection_status === "connected" ? "Manage" : "Set up"}</Button>
              : <Button type="primary" disabled={soon || p.connection_ids.length > 0} onClick={() => { form.resetFields(); setConnecting(p); }}>{soon ? "Coming soon" : "Connect"}</Button>}
            {p.docs_url && <Typography.Link href={p.docs_url} target="_blank">Docs</Typography.Link>}
          </Space>
        </Card>
      </Col>
    );
  };

  const mon = monitor.data;
  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Typography.Title level={3} style={{ margin: 0 }}>Integrations</Typography.Title>
      <Alert type="info" showIcon message="Each app is a separate adapter. What it can do depends on the provider's own API, permissions and terms. Items marked Coming soon do nothing yet." />
      <Tabs items={[
        { key: "market", label: "Marketplace", children: (
          <Space direction="vertical" style={{ width: "100%" }} size={12}>
            <Space wrap>
              <Input.Search allowClear placeholder="Search apps" onChange={(e) => setSearch(e.target.value)} style={{ width: 240 }} />
              <Select value={category} onChange={setCategory} style={{ width: 200 }} options={categories.map((c) => ({ value: c, label: c }))} />
            </Space>
            {visible.length === 0 ? <Empty /> : <Row gutter={[16, 16]}>{visible.map(card)}</Row>}
          </Space>) },
        { key: "connected", label: "Connected apps", children: (
          <Table size="small" rowKey="id" dataSource={(connections.data ?? []).filter((c) => c.status !== "disabled")} locale={{ emptyText: "No connections yet" }} pagination={false}
            columns={[
              { title: "App", dataIndex: "provider", render: nameOf },
              { title: "Scope", dataIndex: "restaurant_id", render: (r: number | null) => (r ? `Outlet #${r}` : "All outlets") },
              { title: "Status", render: (_: unknown, c: Connection) => <Space><Tag color={statusColor[c.status]}>{c.status}</Tag>{c.circuit_open && <Tag color="orange">paused after repeated failures</Tag>}</Space> },
              { title: "Last sync", dataIndex: "last_sync_at", render: fmt },
              { title: "Send updates", render: (_: unknown, c: Connection) => (
                <Switch checked={c.config?.sync_outbound !== false} onChange={(v) => act.mutate({ path: `/integrations/connections/${c.id}`, method: "PATCH", body: { sync_outbound: v } })} />) },
              { title: "", render: (_: unknown, c: Connection) => (
                <Space>
                  <Button size="small" onClick={() => act.mutate({ path: `/integrations/connections/${c.id}/test` })}>Test</Button>
                  <Popconfirm title="Rotate the webhook URL? The old one stops working." onConfirm={() => act.mutate({ path: `/integrations/connections/${c.id}/rotate`, body: {} })}><Button size="small">Rotate URL</Button></Popconfirm>
                  <Popconfirm title="Disconnect and delete stored credentials?" onConfirm={() => act.mutate({ path: `/integrations/connections/${c.id}`, method: "DELETE" })}><Button size="small" danger>Disconnect</Button></Popconfirm>
                </Space>) },
            ]} />) },
        { key: "activity", label: "Sync history", children: (
          <Space direction="vertical" style={{ width: "100%" }} size={16}>
            <Card size="small" title="Jobs">
              <Table size="small" rowKey="id" dataSource={jobs.data ?? []} pagination={{ pageSize: 8 }}
                columns={[{ title: "App", dataIndex: "connection_id", render: (id: number) => nameOf(connections.data?.find((c) => c.id === id)?.provider ?? "") },
                  { title: "Operation", dataIndex: "operation" }, { title: "Status", dataIndex: "status", render: (s: string) => <Tag color={statusColor[s]}>{s}</Tag> },
                  { title: "Attempts", dataIndex: "attempts" }, { title: "Error", dataIndex: "error_message" },
                  { title: "", render: (_: unknown, j: Job) => (j.status === "dead" || j.status === "pending") && j.attempts > 0 && <Button size="small" onClick={() => act.mutate({ path: `/integrations/jobs/${j.id}/retry` })}>Retry</Button> }]} />
            </Card>
            <Card size="small" title="Webhook events (sensitive fields masked)">
              <Table size="small" rowKey="id" dataSource={events.data ?? []} pagination={{ pageSize: 8 }}
                expandable={{ expandedRowRender: (e) => <pre style={{ margin: 0, maxHeight: 200, overflow: "auto" }}>{JSON.stringify(e.payload, null, 2)}</pre> }}
                columns={[{ title: "Time", dataIndex: "created_at", render: fmt }, { title: "App", dataIndex: "provider", render: nameOf }, { title: "Event", dataIndex: "event_type" },
                  { title: "Status", dataIndex: "processing_status", render: (s: string) => <Tag color={statusColor[s]}>{s}</Tag> }, { title: "Error", dataIndex: "error" }]} />
            </Card>
          </Space>) },
        { key: "monitor", label: "Monitoring", children: mon ? (
          <Space direction="vertical" style={{ width: "100%" }} size={16}>
            <Row gutter={16}>
              <Col span={6}><Card><Statistic title="Connections" value={mon.connections} suffix={`(${mon.active} active)`} /></Card></Col>
              <Col span={6}><Card><Statistic title="Pending jobs" value={mon.jobs.pending + mon.jobs.running} /></Card></Col>
              <Col span={6}><Card><Statistic title="Successful syncs" value={mon.jobs.succeeded} /></Card></Col>
              <Col span={6}><Card><Statistic title="Failed (dead-letter)" value={mon.jobs.dead} valueStyle={mon.jobs.dead ? { color: "#cf1322" } : undefined} /></Card></Col>
            </Row>
            <Descriptions bordered size="small" column={1}>
              <Descriptions.Item label="Last successful sync">{fmt(mon.last_successful_sync)}</Descriptions.Item>
              <Descriptions.Item label="Webhook events, last 24h">{Object.entries(mon.events_24h).map(([k, v]) => `${k}: ${v}`).join(" · ") || "none"}</Descriptions.Item>
            </Descriptions>
            {mon.errors.map((e) => <Alert key={e.id} type="error" showIcon message={`${nameOf(e.provider)}: ${e.error}`} description={e.circuit_open ? "Sending is paused for a few minutes after repeated failures." : undefined} />)}
          </Space>) : null },
      ]} />

      <Modal open={!!connecting} title={`Connect ${connecting?.name ?? ""}`} onCancel={() => setConnecting(null)} onOk={() => form.submit()} confirmLoading={connect.isPending} okText="Connect">
        <Form form={form} layout="vertical" initialValues={{ scope: "outlet" }} onFinish={(v) => { const { scope, ...credentials } = v; connect.mutate({ credentials, scope }); }}>
          {connecting?.credential_fields.map((f) => (
            <Form.Item key={f.key} name={f.key} label={f.label} extra={f.help} rules={[{ required: f.required }]}>{f.secret ? <Input.Password autoComplete="off" /> : <Input autoComplete="off" />}</Form.Item>
          ))}
          <Form.Item name="scope" label="Applies to"><Radio.Group options={[{ value: "outlet", label: "This outlet only" }, { value: "all", label: "All outlets" }]} /></Form.Item>
          <Typography.Text type="secondary">Credentials are encrypted and never shown again.</Typography.Text>
        </Form>
      </Modal>
      <Modal open={!!shown} title={shown?.name} onCancel={() => setShown(null)} onOk={() => setShown(null)} cancelButtonProps={{ style: { display: "none" } }}>
        <Alert type="warning" showIcon style={{ marginBottom: 12 }} message="Copy this URL now. It is shown only once." />
        <Typography.Text code copyable>{shown?.url}</Typography.Text>
      </Modal>
    </Space>
  );
}

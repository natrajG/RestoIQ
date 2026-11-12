import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Form, Input, InputNumber, Popconfirm, Table, Tag, Typography, message } from "antd";
import type { Outlet } from "../../pos/api";
import { tablesApi, type AdminTable } from "../api";

export function TablesPage({ outlet }: { outlet: Outlet }) {
  const queryClient = useQueryClient();
  const [bulkForm] = Form.useForm();
  const [oneForm] = Form.useForm();
  const key = ["admin-tables", outlet.id];
  const tables = useQuery({ queryKey: key, queryFn: () => tablesApi.list(outlet.id) });
  const done = (text: string) => { message.success(text); void queryClient.invalidateQueries({ queryKey: key }); void queryClient.invalidateQueries({ queryKey: ["tables"] }); };
  const fail = (e: Error) => message.error(e.message);
  const bulk = useMutation({ mutationFn: (v: { prefix: string; count: number; seats: number; floor_name?: string }) => tablesApi.bulk(outlet.id, v),
    onSuccess: (r) => done(`${r.created.length} tables added`), onError: fail });
  const one = useMutation({ mutationFn: (v: { name: string; seats: number; floor_name?: string }) => tablesApi.create(outlet.id, v),
    onSuccess: () => { oneForm.resetFields(["name"]); done("Table added"); }, onError: fail });
  const seats = useMutation({ mutationFn: ({ id, n }: { id: number; n: number }) => tablesApi.update(outlet.id, id, { seats: n }), onSuccess: () => done("Seats updated"), onError: fail });
  const remove = useMutation({ mutationFn: (id: number) => tablesApi.remove(outlet.id, id), onSuccess: () => done("Table removed"), onError: fail });
  const rows = tables.data?.tables ?? [];

  return (
    <div className="page">
      <div className="page-heading"><div><Typography.Title level={2}>Tables & floor</Typography.Title>
        <Typography.Paragraph type="secondary">Set up the tables for {outlet.name}. Names should match the numbers on your physical tables, as cameras and staff tasks refer to them.</Typography.Paragraph></div></div>
      {!rows.length && !tables.isLoading && <Alert className="service-banner" type="warning" showIcon message="No tables yet" description="Add your tables below to start floor monitoring and staff tasks." />}
      <Card title="Add many tables at once" className="section-card">
        <Form form={bulkForm} layout="inline" initialValues={{ prefix: "T", count: 10, seats: 4, floor_name: "Main Floor" }} onFinish={(v) => bulk.mutate(v)}>
          <Form.Item name="prefix" label="Name prefix"><Input style={{ width: 80 }} maxLength={8} /></Form.Item>
          <Form.Item name="count" label="How many" rules={[{ required: true }]}><InputNumber min={1} max={100} /></Form.Item>
          <Form.Item name="seats" label="Seats each"><InputNumber min={1} max={50} /></Form.Item>
          <Form.Item name="floor_name" label="Floor"><Input style={{ width: 160 }} /></Form.Item>
          <Button type="primary" htmlType="submit" loading={bulk.isPending}>Add tables</Button>
        </Form>
        <Typography.Paragraph type="secondary" style={{ marginTop: 8 }}>Creates T01, T02, … skipping names that already exist.</Typography.Paragraph>
      </Card>
      <Card title="Add one table" className="section-card">
        <Form form={oneForm} layout="inline" initialValues={{ seats: 4, floor_name: "Main Floor" }} onFinish={(v) => one.mutate(v)}>
          <Form.Item name="name" label="Name" rules={[{ required: true }]}><Input style={{ width: 120 }} maxLength={48} /></Form.Item>
          <Form.Item name="seats" label="Seats"><InputNumber min={1} max={50} /></Form.Item>
          <Form.Item name="floor_name" label="Floor"><Input style={{ width: 160 }} /></Form.Item>
          <Button htmlType="submit" loading={one.isPending}>Add</Button>
        </Form>
      </Card>
      <Card title={`Tables (${rows.length})`} className="section-card">
        <Table<AdminTable> rowKey="id" size="small" loading={tables.isLoading} dataSource={rows} pagination={{ pageSize: 15, hideOnSinglePage: true }}
          columns={[
            { title: "Table", dataIndex: "name" },
            { title: "Floor", dataIndex: "floor_name", render: (v: string | null) => v ?? "—" },
            { title: "Seats", dataIndex: "seats", render: (n: number, r) => <InputNumber min={1} max={50} defaultValue={n} key={`${r.id}-${n}`} onBlur={(e) => { const v = Number(e.target.value); if (v && v !== n) seats.mutate({ id: r.id, n: v }); }} /> },
            { title: "Status", dataIndex: "status", render: (s: string) => <Tag>{s}</Tag> },
            { title: "", render: (_, r) => <Popconfirm title={`Remove ${r.name}?`} onConfirm={() => remove.mutate(r.id)}><Button size="small" danger>Remove</Button></Popconfirm> },
          ]} />
      </Card>
    </div>
  );
}

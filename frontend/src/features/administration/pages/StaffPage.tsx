import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Form, Input, Modal, Select, Switch, Table, Tag, Typography, message } from "antd";
import { useState } from "react";
import type { Outlet } from "../../pos/api";
import { staffApi, type StaffMember } from "../api";

const ROLE_ACCESS: Record<string, string> = {
  manager: "Floor, tasks, kitchen, POS, analytics, cameras, POS connection, staff (non-managers)",
  cashier: "Native POS and staff tasks",
  waiter: "Native POS, live floor, kitchen and staff tasks",
  kitchen: "Kitchen display and staff tasks",
  cleaner: "Live floor and cleaning tasks",
  analyst: "Overview and sales analytics (read only)",
};

export function StaffPage({ outlets, canAssignManagers }: { outlets: Outlet[]; canAssignManagers: boolean }) {
  const queryClient = useQueryClient();
  const [form] = Form.useForm();
  const [editForm] = Form.useForm();
  const [editing, setEditing] = useState<StaffMember | null>(null);
  const staff = useQuery({ queryKey: ["staff"], queryFn: staffApi.list });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["staff"] });
  const create = useMutation({
    mutationFn: staffApi.create,
    onSuccess: () => { message.success("Staff account created"); form.resetFields(); void refresh(); },
    onError: (error: Error) => message.error(error.message),
  });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Parameters<typeof staffApi.update>[1] }) => staffApi.update(id, body),
    onSuccess: () => { setEditing(null); void refresh(); },
    onError: (error: Error) => message.error(error.message),
  });
  const roles = staff.data?.assignable_roles ?? [];
  const outletName = (id: number) => outlets.find((o) => o.id === id)?.name ?? `#${id}`;

  return (
    <div className="page">
      <div className="page-heading"><div><Typography.Title level={2}>Staff & access</Typography.Title>
        <Typography.Paragraph type="secondary">Create logins for your team. Each person only sees the screens for their role, at the outlets you choose.</Typography.Paragraph></div></div>
      <Card title="Add staff member" className="section-card">
        <Form form={form} layout="vertical" onFinish={(v) => create.mutate(v)} requiredMark={false}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 16 }}>
            <Form.Item name="full_name" label="Full name"><Input autoComplete="off" /></Form.Item>
            <Form.Item name="email" label="Email (login)" rules={[{ required: true, type: "email" }]}><Input autoComplete="off" /></Form.Item>
            <Form.Item name="role" label="Role" rules={[{ required: true }]}>
              <Select options={roles.map((r) => ({ value: r, label: r }))} placeholder="Select role" />
            </Form.Item>
            <Form.Item name="outlet_ids" label="Outlets" rules={[{ required: true, message: "Pick at least one outlet" }]}>
              <Select mode="multiple" options={outlets.map((o) => ({ value: o.id, label: o.name }))} />
            </Form.Item>
            <Form.Item name="password" label="Temporary password" rules={[{ required: true, min: 8 }]}><Input.Password autoComplete="new-password" /></Form.Item>
          </div>
          <Form.Item noStyle shouldUpdate>{() => form.getFieldValue("role") && <Alert type="info" showIcon style={{ marginBottom: 12 }} message={`Access: ${ROLE_ACCESS[form.getFieldValue("role")] ?? ""}`} />}</Form.Item>
          {!canAssignManagers && <Typography.Paragraph type="secondary">Only the owner can create manager accounts.</Typography.Paragraph>}
          <Button type="primary" htmlType="submit" loading={create.isPending}>Create account</Button>
        </Form>
      </Card>
      <Card title="Your team" className="section-card">
        <Table<StaffMember> rowKey="id" loading={staff.isLoading} dataSource={staff.data?.staff ?? []} pagination={false} scroll={{ x: true }}
          locale={{ emptyText: "No staff yet" }}
          columns={[
            { title: "Name", dataIndex: "full_name", render: (v: string | null) => v ?? "—" },
            { title: "Email", dataIndex: "email" },
            { title: "Role", dataIndex: "role", render: (r: string) => <Tag color="blue">{r}</Tag> },
            { title: "Outlets", dataIndex: "outlet_ids", render: (ids: number[]) => ids.map((id) => <Tag key={id}>{outletName(id)}</Tag>) },
            { title: "Active", dataIndex: "is_active", render: (v: boolean, row) => (
              <Switch checked={v} disabled={row.role === "manager" && !canAssignManagers} onChange={(checked) => update.mutate({ id: row.id, body: { is_active: checked } })} />) },
            { title: "", render: (_, row) => (
              <Button size="small" disabled={row.role === "manager" && !canAssignManagers}
                onClick={() => { setEditing(row); editForm.setFieldsValue({ full_name: row.full_name, role: row.role, outlet_ids: row.outlet_ids, password: undefined }); }}>Edit</Button>) },
          ]} />
      </Card>
      <Modal title={`Edit ${editing?.email ?? ""}`} open={!!editing} onCancel={() => setEditing(null)} okText="Save" confirmLoading={update.isPending}
        onOk={() => editForm.validateFields().then((v) => editing && update.mutate({ id: editing.id, body: { ...v, password: v.password || undefined } }))}>
        <Form form={editForm} layout="vertical" requiredMark={false}>
          <Form.Item name="full_name" label="Full name"><Input /></Form.Item>
          <Form.Item name="role" label="Role" rules={[{ required: true }]}><Select options={roles.map((r) => ({ value: r, label: r }))} /></Form.Item>
          <Form.Item name="outlet_ids" label="Outlets" rules={[{ required: true, message: "Pick at least one outlet" }]}>
            <Select mode="multiple" options={outlets.map((o) => ({ value: o.id, label: o.name }))} />
          </Form.Item>
          <Form.Item name="password" label="Reset password (leave blank to keep)" rules={[{ min: 8 }]}><Input.Password autoComplete="new-password" /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

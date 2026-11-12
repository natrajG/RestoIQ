import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, DatePicker, Drawer, Form, Input, InputNumber, Select, Table, Tag, Typography, message } from "antd";
import dayjs from "dayjs";
import { customerApi, ledgerApi, type Customer } from "../api";

export function CustomersPage({ outletId }: { outletId: number }) {
  const client = useQueryClient();
  const [q, setQ] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);
  const [form] = Form.useForm();
  const [txn] = Form.useForm();
  const list = useQuery({ queryKey: ["customers", outletId, q], queryFn: () => customerApi.list(outletId, q) });
  const detail = useQuery({
    queryKey: ["customer", openId], enabled: openId !== null,
    queryFn: async () => { const d = await customerApi.detail(openId as number); form.setFieldsValue({ ...d, birthday: d.birthday ? dayjs(d.birthday) : null, anniversary: d.anniversary ? dayjs(d.anniversary) : null }); return d; },
  });
  const save = useMutation({
    mutationFn: (v: Record<string, unknown>) => customerApi.update(openId as number, {
      name: String(v.name), phone: (v.phone as string) || null, email: (v.email as string) || null, gstin: (v.gstin as string) || null, address: (v.address as string) || null,
      birthday: v.birthday ? (v.birthday as dayjs.Dayjs).format("YYYY-MM-DD") : null, anniversary: v.anniversary ? (v.anniversary as dayjs.Dayjs).format("YYYY-MM-DD") : null,
    }),
    onSuccess: () => { message.success("Customer saved"); void client.invalidateQueries({ queryKey: ["customers", outletId] }); void client.invalidateQueries({ queryKey: ["customer", openId] }); },
    onError: (e: Error) => message.error(e.message),
  });
  const ledger = useQuery({ queryKey: ["ledger", openId], enabled: openId !== null, queryFn: () => ledgerApi.get(openId as number) });
  const addTxn = useMutation({
    mutationFn: (v: { kind: "credit" | "debit"; amount: number; method?: string; remark?: string }) => ledgerApi.add(openId as number, v),
    onSuccess: (d) => { client.setQueryData(["ledger", openId], d); void client.invalidateQueries({ queryKey: ["customers", outletId] }); txn.resetFields(); message.success("Entry added"); },
    onError: (e: Error) => message.error(e.message),
  });
  return (
    <div className="page">
      <div className="page-heading"><div><Typography.Title level={2}>Customers</Typography.Title>
        <Typography.Paragraph type="secondary">Customers are added automatically when you enter a phone number on an order.</Typography.Paragraph></div></div>
      <Card>
        <Input.Search allowClear placeholder="Search by name or phone" onSearch={setQ} style={{ maxWidth: 360, marginBottom: 12 }} />
        <Table<Customer> size="middle" rowKey="id" loading={list.isLoading} dataSource={list.data ?? []} onRow={(r) => ({ onClick: () => setOpenId(r.id), style: { cursor: "pointer" } })}
          locale={{ emptyText: "No customers yet" }}
          columns={[{ title: "Name", dataIndex: "name" }, { title: "Phone", dataIndex: "phone" }, { title: "Orders", dataIndex: "orders" },
            { title: "Spent", dataIndex: "spent", render: (v: string) => Number(v ?? 0).toFixed(2) },
            { title: "Last visit", dataIndex: "last_visit", render: (v: string | null) => (v ? dayjs(v).format("DD MMM YYYY") : "—") },
            { title: "Balance due", dataIndex: "balance_due", render: (v: string) => (Number(v) > 0 ? <Tag color="red">{Number(v).toFixed(2)}</Tag> : "—") },
            { title: "Points", dataIndex: "loyalty_points", render: (p: number) => <Tag>{p}</Tag> }]} />
      </Card>
      <Drawer open={openId !== null} width={480} title={detail.data?.name ?? "Customer"} onClose={() => setOpenId(null)} destroyOnClose>
        <Form form={form} layout="vertical" onFinish={(v) => save.mutate(v)}>
          <Form.Item name="name" label="Name" rules={[{ required: true }]}><Input maxLength={200} /></Form.Item>
          <Form.Item name="phone" label="Mobile"><Input maxLength={20} /></Form.Item>
          <Form.Item name="email" label="Email"><Input maxLength={254} /></Form.Item>
          <Form.Item name="birthday" label="Birthday"><DatePicker style={{ width: "100%" }} /></Form.Item>
          <Form.Item name="anniversary" label="Anniversary"><DatePicker style={{ width: "100%" }} /></Form.Item>
          <Form.Item name="gstin" label="GSTIN (for B2B bills)" rules={[{ pattern: /^[0-9A-Za-z]{15}$/, message: "GSTIN is 15 characters" }]}><Input maxLength={15} /></Form.Item>
          <Form.Item name="address" label="Address"><Input.TextArea rows={2} maxLength={400} /></Form.Item>
          <Button type="primary" htmlType="submit" loading={save.isPending}>Save</Button>
        </Form>
        <Typography.Title level={5} style={{ marginTop: 24 }}>Customer account {ledger.data && <Tag color={Number(ledger.data.balance_due) > 0 ? "red" : "green"}>Due {Number(ledger.data.balance_due).toFixed(2)}</Tag>}</Typography.Title>
        <Form form={txn} layout="inline" initialValues={{ kind: "credit", method: "cash" }} onFinish={(v) => addTxn.mutate(v)} style={{ rowGap: 8, marginBottom: 12 }}>
          <Form.Item name="kind"><Select style={{ width: 130 }} options={[{ value: "credit", label: "Money received" }, { value: "debit", label: "Manual charge" }]} /></Form.Item>
          <Form.Item name="amount" rules={[{ required: true, message: "Amount" }]}><InputNumber min={1} placeholder="Amount" /></Form.Item>
          <Form.Item name="method"><Select style={{ width: 90 }} options={["cash", "upi", "card", "bank"].map((c) => ({ value: c, label: c }))} /></Form.Item>
          <Form.Item name="remark"><Input placeholder="Remark" maxLength={200} /></Form.Item>
          <Button htmlType="submit" loading={addTxn.isPending}>Add</Button>
        </Form>
        <Table size="small" rowKey="id" pagination={{ pageSize: 8, hideOnSinglePage: true }} dataSource={ledger.data?.entries ?? []} locale={{ emptyText: "No account activity" }}
          columns={[{ title: "Date", dataIndex: "created_at", render: (v: string) => dayjs(v).format("DD MMM") },
            { title: "Type", dataIndex: "kind", render: (k: string) => (k === "debit" ? <Tag color="red">Charged</Tag> : <Tag color="green">Received</Tag>) },
            { title: "Amount", dataIndex: "amount" }, { title: "Note", dataIndex: "remark" }]} />
        <Typography.Title level={5} style={{ marginTop: 24 }}>Order history</Typography.Title>
        <Table size="small" rowKey="id" pagination={false} dataSource={detail.data?.orders ?? []} locale={{ emptyText: "No orders" }}
          columns={[{ title: "Bill", dataIndex: "order_number" }, { title: "Date", dataIndex: "created_at", render: (v: string) => dayjs(v).format("DD MMM") },
            { title: "Items", dataIndex: "items", render: (i: string[]) => i.join(", ") }, { title: "Total", dataIndex: "total" }]} />
      </Drawer>
    </div>
  );
}

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Col, Form, Input, InputNumber, Popconfirm, Radio, Row, Select, Statistic, Table, Tag, Typography, message } from "antd";
import { cashApi, orderApi, type Cashbook, type CashEntry } from "../api";

export function DayClosePage({ outletId, currency, canDelete }: { outletId: number; currency: string; canDelete: boolean }) {
  const client = useQueryClient();
  const book = useQuery({ queryKey: ["cashbook", outletId], queryFn: () => cashApi.book(outletId) });
  const history = useQuery({ queryKey: ["day-closes", outletId], queryFn: () => cashApi.history(outletId) });
  const [petty] = Form.useForm();
  const [close] = Form.useForm();
  const [diff, setDiff] = useState(0);
  const m = (v: string | number) => `${currency} ${Number(v).toFixed(2)}`;
  const refresh = (data: Cashbook) => { client.setQueryData(["cashbook", outletId], data); void client.invalidateQueries({ queryKey: ["day-closes", outletId] }); };
  const fail = (e: Error) => message.error(e.message);
  const add = useMutation({ mutationFn: (v: { kind: "in" | "out"; amount: number; reason: string; category?: string; pay_method?: string }) => cashApi.addPetty(outletId, v), onSuccess: (d) => { refresh(d); petty.resetFields(); message.success("Entry added"); }, onError: fail });
  const remove = useMutation({ mutationFn: (id: number) => cashApi.removePetty(outletId, id), onSuccess: refresh, onError: fail });
  const closeDay = useMutation({ mutationFn: (v: { opening_cash?: number; counted_cash: number; note?: string }) => cashApi.close(outletId, v), onSuccess: (d) => { refresh(d); message.success("Day closed"); }, onError: fail });
  const voidOrder = useMutation({ mutationFn: (id: number) => orderApi.void(id, "Voided at day close"), onSuccess: () => { void client.invalidateQueries({ queryKey: ["cashbook", outletId] }); message.success("Order voided"); }, onError: fail });
  const b = book.data;
  const blocked = (b?.unsettled.length ?? 0) > 0;
  const expected = b ? Number(b.expected_cash) + (b.opening_known ? 0 : Number(close.getFieldValue("opening_cash") ?? 0)) : 0;
  return (
    <div className="page">
      <div className="page-heading"><div><Typography.Title level={2}>Day close & cash</Typography.Title>
        <Typography.Paragraph type="secondary">Track cash taken in and paid out, then count the drawer at the end of the day.</Typography.Paragraph></div>{b && <Tag color={b.closed ? "green" : "orange"}>{b.closed ? "Closed" : "Open"} · {b.date}</Tag>}</div>
      {b && (
        <>
          <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
            <Col xs={12} md={6}><Card><Statistic title="Opening cash" value={m(b.opening_cash)} /></Card></Col>
            <Col xs={12} md={6}><Card><Statistic title="Cash sales" value={m(b.cash_sales)} /></Card></Col>
            <Col xs={12} md={6}><Card><Statistic title="Petty cash in / out" value={`${Number(b.petty_in).toFixed(0)} / ${Number(b.petty_out).toFixed(0)}`} /></Card></Col>
            <Col xs={12} md={6}><Card><Statistic title="Cash that should be in drawer" value={m(b.expected_cash)} /></Card></Col>
          </Row>
          {blocked && !b.closed && <Alert type="error" showIcon style={{ marginBottom: 16 }} message={`${b.unsettled.length} order(s) must be paid or voided before closing the day`}
            description={<div>{b.unsettled.map((o) => <div key={o.id} className="provider-row"><span>{o.order_number} · {o.order_type.replace("_", " ")} · {m(o.total)} · {o.status.replace("_", " ")}</span>
              <Popconfirm title="Void this order?" onConfirm={() => voidOrder.mutate(o.id)}><Button size="small" danger>Void</Button></Popconfirm></div>)}</div>} />}
          {Number(b.account_cash) > 0 && <Alert type="info" showIcon style={{ marginBottom: 16 }} message={`Includes ${m(b.account_cash)} cash received against customer accounts today.`} />}
          {b.unpaid_orders > 0 && !blocked && !b.closed && <Alert type="warning" showIcon style={{ marginBottom: 16 }} message={`${b.unpaid_orders} order(s) today are not paid yet. You can still close the day.`} />}
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={12}>
              <Card title="Petty cash">
                {!b.closed && (
                  <Form form={petty} layout="inline" onFinish={(v) => add.mutate(v)} initialValues={{ kind: "out", pay_method: "cash" }} style={{ marginBottom: 12, rowGap: 8 }}>
                    <Form.Item name="kind"><Radio.Group optionType="button" options={[{ value: "out", label: "Paid out" }, { value: "in", label: "Cash in" }]} /></Form.Item>
                    <Form.Item name="amount" rules={[{ required: true, message: "Amount" }]}><InputNumber min={1} placeholder="Amount" /></Form.Item>
                    <Form.Item name="category"><Select allowClear placeholder="Category" style={{ width: 140 }} options={(b.categories ?? []).map((c) => ({ value: c, label: c }))} /></Form.Item>
                    <Form.Item name="pay_method"><Select style={{ width: 90 }} options={["cash", "upi", "card", "bank"].map((c) => ({ value: c, label: c }))} /></Form.Item>
                    <Form.Item name="reason" rules={[{ required: true, message: "Reason" }]}><Input placeholder="Reason (e.g. milk, gas)" maxLength={200} /></Form.Item>
                    <Button htmlType="submit" type="primary" loading={add.isPending}>Add</Button>
                  </Form>)}
                <Table<CashEntry> size="small" rowKey="id" pagination={false} dataSource={b.entries} locale={{ emptyText: "No petty cash entries today" }}
                  columns={[
                    { title: "Type", dataIndex: "kind", render: (k: string) => <Tag color={k === "in" ? "green" : "red"}>{k === "in" ? "In" : "Out"}</Tag> },
                    { title: "Amount", dataIndex: "amount", render: m },
                    { title: "Reason", dataIndex: "reason", render: (r: string, e: CashEntry) => `${r}${e.category ? ` · ${e.category}` : ""}${e.pay_method && e.pay_method !== "cash" ? ` (${e.pay_method}, not from drawer)` : ""}` },
                    { title: "By", dataIndex: "created_by" },
                    ...(canDelete && !b.closed ? [{ title: "", key: "x", render: (_: unknown, r: CashEntry) => <Popconfirm title="Delete entry?" onConfirm={() => remove.mutate(r.id)}><Button size="small" type="link" danger>Delete</Button></Popconfirm> }] : []),
                  ]} />
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card title="Close the day">
                {b.closed ? (
                  <Alert type={Number(b.closed.difference) === 0 ? "success" : "warning"} showIcon message={`Closed by ${b.closed.closed_by ?? "staff"}: counted ${m(b.closed.counted_cash)}, difference ${m(b.closed.difference)}`} description={b.closed.note ?? undefined} />
                ) : (
                  <Form form={close} layout="vertical" onFinish={(v) => closeDay.mutate({ ...v, note: v.note?.trim() || undefined })}
                    onValuesChange={(_, all) => setDiff(Number(all.counted_cash ?? 0) - (Number(b.expected_cash) + (b.opening_known ? 0 : Number(all.opening_cash ?? 0))))}>
                    {!b.opening_known && <Form.Item name="opening_cash" label="Opening cash (first day only)" rules={[{ required: true, message: "Enter the cash you started with" }]}><InputNumber min={0} style={{ width: "100%" }} /></Form.Item>}
                    <Form.Item name="counted_cash" label="Cash counted in drawer" rules={[{ required: true, message: "Enter the counted cash" }]}><InputNumber min={0} style={{ width: "100%" }} /></Form.Item>
                    {close.getFieldValue("counted_cash") !== undefined && <Typography.Paragraph type={diff === 0 ? "success" : "danger"}>{diff === 0 ? "Cash matches." : `Difference: ${m(diff)} (expected ${m(expected)})`}</Typography.Paragraph>}
                    <Form.Item name="note" label="Note (required if there is a difference)"><Input.TextArea rows={2} maxLength={300} /></Form.Item>
                    <Popconfirm title="Close today? This cannot be undone." onConfirm={() => close.submit()}><Button type="primary" disabled={blocked} loading={closeDay.isPending}>Close day</Button></Popconfirm>
                  </Form>)}
              </Card>
            </Col>
          </Row>
        </>)}
      <Card title="Previous days" style={{ marginTop: 16 }}>
        <Table size="small" rowKey="date" loading={history.isLoading} dataSource={history.data ?? []} pagination={{ pageSize: 10 }}
          columns={[{ title: "Date", dataIndex: "date" }, { title: "Opening", dataIndex: "opening_cash", render: m }, { title: "Cash sales", dataIndex: "cash_sales", render: m },
            { title: "Expected", dataIndex: "expected_cash", render: m }, { title: "Counted", dataIndex: "counted_cash", render: m },
            { title: "Difference", dataIndex: "difference", render: (d: string) => <Tag color={Number(d) === 0 ? "green" : "red"}>{m(d)}</Tag> },
            { title: "Closed by", dataIndex: "closed_by" }, { title: "Note", dataIndex: "note" }]} />
      </Card>
    </div>
  );
}

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Col, DatePicker, Row, Space, Statistic, Table, Typography } from "antd";
import dayjs from "dayjs";
import { salesApi } from "../api";

export function SalesSummaryPage({ outletId, currency }: { outletId: number; currency: string }) {
  const [range, setRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([dayjs(), dayjs()]);
  const from = range[0].format("YYYY-MM-DD");
  const to = range[1].format("YYYY-MM-DD");
  const q = useQuery({ queryKey: ["sales-summary", outletId, from, to], queryFn: () => salesApi.summary(outletId, from, to) });
  const m = (v: string | number) => `${currency} ${Number(v).toFixed(2)}`;
  const d = q.data;
  const cards: [string, string | undefined][] = d ? [["Bills", String(d.bills)], ["Subtotal", d.subtotal], ["Complimentary", d.complimentary], ["Discount", d.discount], ["Tax", d.tax],
    ["Service charge", d.service_charge], ["Round off", d.round_off], ["Total sale", d.total_sale], ["Pending collection", d.pending_collection], ["Refunds", d.refunds]] : [];
  return (
    <div className="page">
      <div className="page-heading"><div><Typography.Title level={2}>Sales summary</Typography.Title>
        <Typography.Paragraph type="secondary">Sales by payment method, order type and item category for any date range.</Typography.Paragraph></div>
        <Space>
          <DatePicker.RangePicker allowClear={false} value={range} onChange={(v) => v?.[0] && v[1] && setRange([v[0], v[1]])} />
          <Button onClick={() => window.print()}>Print</Button>
        </Space></div>
      {d && (
        <>
          <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
            {cards.map(([t, v]) => <Col xs={12} md={6} key={t}><Card loading={q.isLoading}><Statistic title={t} value={t === "Bills" ? v : m(v ?? 0)} /></Card></Col>)}
          </Row>
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={8}><Card title="By payment method"><Table size="small" rowKey="method" pagination={false} dataSource={d.by_method}
              columns={[{ title: "Method", dataIndex: "method", render: (v: string) => v.replace("_external", "").replace("_", " ") }, { title: "Bills", dataIndex: "count" }, { title: "Amount", dataIndex: "amount", render: m }]} /></Card></Col>
            <Col xs={24} lg={8}><Card title="By order type"><Table size="small" rowKey="type" pagination={false} dataSource={d.by_type}
              columns={[{ title: "Type", dataIndex: "type", render: (v: string) => v.replace("_", " ") }, { title: "Bills", dataIndex: "count" }, { title: "Amount", dataIndex: "amount", render: m }]} /></Card></Col>
            <Col xs={24} lg={8}><Card title="By item category"><Table size="small" rowKey="group" pagination={false} dataSource={d.by_group}
              columns={[{ title: "Category", dataIndex: "group" }, { title: "Qty", dataIndex: "quantity" }, { title: "Amount", dataIndex: "amount", render: m }]} /></Card></Col>
          </Row>
          <Card title="Payment reconciliation" style={{ marginTop: 16 }}>
            <Row gutter={[12, 12]}>
              {([["Billed (incl. tips)", d.reconciliation.billed], ["Collected", d.reconciliation.collected], ["Refunds", d.reconciliation.refunds], ["Net collected", d.reconciliation.net_collected],
                ["On customer account", d.reconciliation.on_customer_account], ["Advance on open bills", d.reconciliation.advance_on_open_bills], ["Difference", d.reconciliation.difference]] as const).map(([t, v]) => (
                <Col xs={12} md={3} key={t}><Statistic title={t} value={m(v)} /></Col>))}
            </Row>
            {Number(d.reconciliation.difference) !== 0 && <Alert style={{ marginTop: 12 }} type="warning" showIcon message={d.reconciliation.note} />}
          </Card>
          <Card title="Item-wise sales" style={{ marginTop: 16 }} extra={<Button size="small" onClick={() => {
            const csv = ["item,quantity,amount", ...d.by_item.map((r) => `"${r.item.replace(/"/g, '""')}",${r.quantity},${r.amount}`)].join("\n");
            const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" })); a.download = `item-sales-${from}-${to}.csv`; a.click();
          }}>Download CSV</Button>}>
            <Table size="small" rowKey="item" pagination={{ pageSize: 20, hideOnSinglePage: true }} dataSource={d.by_item}
              columns={[{ title: "Item", dataIndex: "item" }, { title: "Qty sold", dataIndex: "quantity", sorter: (a, b) => a.quantity - b.quantity }, { title: "Amount", dataIndex: "amount", sorter: (a, b) => Number(a.amount) - Number(b.amount), render: m }]} />
          </Card>
        </>)}
    </div>
  );
}

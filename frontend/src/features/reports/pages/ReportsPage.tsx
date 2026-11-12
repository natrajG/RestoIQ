import { PrinterOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Col, List, Progress, Row, Segmented, Select, Skeleton, Statistic, Table, Tag, Typography } from "antd";
import { useState } from "react";
import { reportsApi, type Report } from "../api";

const money = (v: string | number | null, c: string) => (v === null ? "—" : `${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 0 })} ${c}`);
const delta = (pct: number | null) => (pct === null ? null : <Tag color={pct >= 0 ? "green" : "red"}>{pct >= 0 ? "+" : ""}{pct}% vs previous</Tag>);

export function ReportsPage({ outletId }: { outletId: number }) {
  const [period, setPeriod] = useState<"weekly" | "monthly">("weekly");
  const [savedId, setSavedId] = useState<number>();
  const live = useQuery({ queryKey: ["report", outletId, period], queryFn: () => reportsApi.live(outletId, period) });
  const saved = useQuery({ queryKey: ["saved-reports", outletId], queryFn: () => reportsApi.saved(outletId) });
  const past = saved.data?.reports.filter((r) => r.period === period) ?? [];
  const chosen = savedId ? past.find((r) => r.id === savedId) : undefined;
  const r: Report | undefined = chosen?.payload ?? live.data;
  const maxDay = Math.max(1, ...(r?.sales.by_weekday ?? []).map((d) => Number(d.revenue)));
  const maxHour = Math.max(1, ...(r?.sales.by_hour ?? []).map((h) => Number(h.revenue)));
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <Typography.Title level={2}>Reports</Typography.Title>
          <Typography.Paragraph type="secondary">Weekly and monthly reports are generated automatically (Mondays and the 1st of each month, 7:00 IST) and saved here. Figures come only from recorded sales, cameras and staff tasks.</Typography.Paragraph>
        </div>
        <div className="no-print" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <Segmented value={period} onChange={(v) => { setPeriod(v as "weekly" | "monthly"); setSavedId(undefined); }} options={[{ value: "weekly", label: "Weekly" }, { value: "monthly", label: "Monthly" }]} />
          <Select style={{ minWidth: 190 }} placeholder="Latest (live)" allowClear value={savedId} onChange={setSavedId}
            options={past.map((p) => ({ value: p.id, label: `Saved ${p.period_end}` }))} />
          <Button icon={<PrinterOutlined />} onClick={() => window.print()}>Print / PDF</Button>
        </div>
      </div>
      {live.isError && <Alert type="error" showIcon message="Report could not be loaded" />}
      {!r ? <Skeleton active /> : (
        <>
          <Card className="section-card" title={`${r.outlet} · last ${r.days} days (${new Date(r.from).toLocaleDateString()} – ${new Date(r.to).toLocaleDateString()})`}>
            <List size="small" dataSource={r.highlights} renderItem={(h) => <List.Item>{h}</List.Item>} />
          </Card>
          <Row gutter={[16, 16]}>
            <Col xs={24} sm={8}><Card><Statistic title="Revenue" value={money(r.sales.revenue, r.currency)} />{delta(r.change.revenue_pct)}</Card></Col>
            <Col xs={24} sm={8}><Card><Statistic title="Bills" value={r.sales.orders} />{delta(r.change.orders_pct)}</Card></Col>
            <Col xs={24} sm={8}><Card><Statistic title="Average bill" value={money(r.sales.average_bill, r.currency)} /></Card></Col>
            <Col xs={24} lg={12}><Card title="Revenue by weekday">{r.sales.by_weekday.map((d) => (
              <div key={d.weekday}><Typography.Text>{d.weekday}</Typography.Text> <Typography.Text type="secondary">{money(d.revenue, r.currency)} · {d.orders} bills</Typography.Text>
                <Progress percent={Math.round((Number(d.revenue) / maxDay) * 100)} showInfo={false} /></div>))}</Card></Col>
            <Col xs={24} lg={12}><Card title="Revenue by hour">{r.sales.by_hour.length ? r.sales.by_hour.map((h) => (
              <div key={h.hour}><Typography.Text>{String(h.hour).padStart(2, "0")}:00</Typography.Text> <Typography.Text type="secondary">{money(h.revenue, r.currency)}</Typography.Text>
                <Progress percent={Math.round((Number(h.revenue) / maxHour) * 100)} showInfo={false} /></div>)) : <Typography.Text type="secondary">No sales recorded.</Typography.Text>}</Card></Col>
            <Col xs={24} lg={12}><Card title="Top items"><Table size="small" pagination={false} rowKey="item" dataSource={r.sales.top_items}
              columns={[{ title: "Item", dataIndex: "item" }, { title: "Qty", dataIndex: "quantity" }, { title: "Revenue", dataIndex: "revenue", render: (v: string) => money(v, r.currency) }]} /></Card></Col>
            <Col xs={24} lg={12}><Card title="Best sellers by weekday"><Table size="small" pagination={false} rowKey="weekday" dataSource={r.sales.top_items_by_weekday.filter((d) => d.items.length)}
              columns={[{ title: "Day", dataIndex: "weekday" }, { title: "Top 3 items", dataIndex: "items", render: (items: { item: string; quantity: number }[]) => items.map((i) => `${i.item} (${i.quantity})`).join(", ") }]} /></Card></Col>
            <Col xs={24} lg={12}><Card title="Table usage (cameras)" extra={<Tag>Unvalidated</Tag>}>
              {r.occupancy.available ? (<>
                <Typography.Paragraph>{r.occupancy.sessions} sessions · average {r.occupancy.avg_dwell_minutes ?? "—"} min</Typography.Paragraph>
                <Table size="small" pagination={false} rowKey="table" dataSource={r.occupancy.busiest_tables}
                  columns={[{ title: "Busiest tables", dataIndex: "table" }, { title: "Sessions", dataIndex: "sessions" }, { title: "Hours", dataIndex: "occupied_hours" }, { title: "Avg min", dataIndex: "avg_minutes" }]} />
              </>) : <Typography.Text type="secondary">No camera data in this period.</Typography.Text>}
              <Typography.Paragraph type="secondary" style={{ marginTop: 8 }}>{r.occupancy.note}</Typography.Paragraph></Card></Col>
            <Col xs={24} lg={12}><Card title="Staff tasks"><Row gutter={16}>
              <Col span={8}><Statistic title="Created" value={r.tasks.created} /></Col>
              <Col span={8}><Statistic title="Completed" value={r.tasks.completed} /></Col>
              <Col span={8}><Statistic title="Overdue" value={r.tasks.overdue} /></Col></Row>
              <Typography.Paragraph type="secondary" style={{ marginTop: 8 }}>Average completion: {r.tasks.avg_completion_minutes ?? "—"} min</Typography.Paragraph></Card></Col>
          </Row>
        </>
      )}
    </div>
  );
}

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, DatePicker, Space, Table, Tag, Typography } from "antd";
import dayjs from "dayjs";
import { exceptionsApi, type ExceptionRow } from "../api";

export function ExceptionsPage({ outletId, currency }: { outletId: number; currency: string }) {
  const [range, setRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([dayjs(), dayjs()]);
  const from = range[0].format("YYYY-MM-DD");
  const to = range[1].format("YYYY-MM-DD");
  const q = useQuery({ queryKey: ["exceptions", outletId, from, to], queryFn: () => exceptionsApi.get(outletId, from, to) });
  const d = q.data;
  const m = (v: string | null) => (v == null ? "-" : `${currency} ${Number(v).toFixed(2)}`);
  const kinds = d ? Object.keys(d.labels) : [];
  const csv = () => {
    if (!d) return;
    const esc = (v: string | null) => `"${(v ?? "").replace(/"/g, '""')}"`;
    const lines = [["Time", "Staff", "Type", "Bill", "Amount", "Reason"].join(","),
      ...d.rows.map((r) => [r.time, r.staff, r.label, r.bill, r.amount, r.reason].map((v) => esc(v as string | null)).join(","))];
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" }));
    a.download = `exceptions-${from}-${to}.csv`;
    a.click();
  };
  return (
    <div className="page">
      <div className="page-heading"><div><Typography.Title level={2}>Exceptions</Typography.Title>
        <Typography.Paragraph type="secondary">Voids, cancelled items, discounts, complimentary items and refunds, by staff member.</Typography.Paragraph></div>
        <Space>
          <DatePicker.RangePicker allowClear={false} value={range} onChange={(v) => v?.[0] && v[1] && setRange([v[0], v[1]])} />
          <Button onClick={csv} disabled={!d?.rows.length}>Download CSV</Button>
        </Space></div>
      <Alert type="info" showIcon style={{ marginBottom: 16 }} message="Unusually high counts for one person are worth a conversation. This report cannot see cash that was never billed or payments sent to a personal QR - always compare with your card machine, UPI app and bank." />
      <Card title="By staff" loading={q.isLoading} style={{ marginBottom: 16 }}>
        <Table size="small" rowKey="staff" pagination={false} dataSource={d?.by_staff ?? []}
          columns={[{ title: "Staff", dataIndex: "staff" }, ...kinds.map((k) => ({ title: d!.labels[k], key: k,
            render: (_: unknown, r: NonNullable<typeof d>["by_staff"][number]) => { const a = r.actions[k]; return a ? `${a.count} (${m(a.amount)})` : "-"; } }))]} />
      </Card>
      <Card title="Details" loading={q.isLoading}>
        <Table<ExceptionRow> size="small" rowKey={(r) => `${r.time}-${r.type}-${r.bill}`} dataSource={d?.rows ?? []} pagination={{ pageSize: 25 }}
          columns={[{ title: "Time", dataIndex: "time", render: (v: string) => dayjs(v).format("DD MMM HH:mm") }, { title: "Staff", dataIndex: "staff" },
            { title: "Type", dataIndex: "label", render: (v: string) => <Tag>{v}</Tag> }, { title: "Bill", dataIndex: "bill" },
            { title: "Amount", dataIndex: "amount", render: m }, { title: "Reason", dataIndex: "reason" }]} />
      </Card>
    </div>
  );
}

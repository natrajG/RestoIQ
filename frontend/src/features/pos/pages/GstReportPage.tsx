import { DownloadOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, DatePicker, Statistic, Row, Col, Table, Typography } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { useState } from "react";
import { menuApi } from "../api";

export function GstReportPage({ outletId, currency }: { outletId: number; currency: string }) {
  const [range, setRange] = useState<[Dayjs, Dayjs]>([dayjs().startOf("month"), dayjs()]);
  const from = range[0].format("YYYY-MM-DD");
  const to = range[1].format("YYYY-MM-DD");
  const report = useQuery({ queryKey: ["gst-report", outletId, from, to], queryFn: () => menuApi.gstReport(outletId, from, to) });
  const r = report.data;
  const m = (v: string) => `${currency} ${Number(v).toFixed(2)}`;
  return (
    <div className="page">
      <div className="page-heading"><div>
        <Typography.Title level={2}>GST & day-end report</Typography.Title>
        <Typography.Paragraph type="secondary">Paid bills by day and GST rate, for your accountant.</Typography.Paragraph>
      </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <DatePicker.RangePicker allowClear={false} value={range} onChange={(v) => v?.[0] && v[1] && setRange([v[0], v[1]])} />
          <Button icon={<DownloadOutlined />} href={`/api/v1/outlets/${outletId}/reports/gst?from=${from}&to=${to}&format=csv`}>Download CSV</Button>
        </div>
      </div>
      {report.isError && <Alert type="error" showIcon message="Report could not be loaded" />}
      {r?.composition && <Alert type="info" showIcon message="This outlet is on the composition scheme: no GST is collected on bills." style={{ marginBottom: 16 }} />}
      {r && (<>
        <Row gutter={[16, 16]}>
          <Col xs={12} md={6}><Card><Statistic title="Bills" value={r.totals.bills} /></Card></Col>
          <Col xs={12} md={6}><Card><Statistic title="Taxable value" value={m(r.totals.taxable)} /></Card></Col>
          <Col xs={12} md={6}><Card><Statistic title="CGST + SGST" value={m(String(Number(r.totals.cgst) + Number(r.totals.sgst)))} /></Card></Col>
          <Col xs={12} md={6}><Card><Statistic title="Total collected" value={m(r.totals.total)} /></Card></Col>
        </Row>
        <Card className="section-card" title="By day and GST rate" style={{ marginTop: 16 }}>
          <Table size="small" rowKey={(x) => `${x.date}-${x.gst_rate}`} dataSource={r.lines} pagination={{ pageSize: 20, hideOnSinglePage: true }}
            columns={[{ title: "Date", dataIndex: "date" }, { title: "GST rate", dataIndex: "gst_rate", render: (v: string) => `${Number(v)}%` },
              { title: "Taxable", dataIndex: "taxable" }, { title: "CGST", dataIndex: "cgst" }, { title: "SGST", dataIndex: "sgst" }]} />
        </Card>
        <Card className="section-card" title="Daily bills" style={{ marginTop: 16 }}>
          <Table size="small" rowKey="date" dataSource={r.daily} pagination={{ pageSize: 20, hideOnSinglePage: true }}
            columns={[{ title: "Date", dataIndex: "date" }, { title: "Bills", dataIndex: "bills" }, { title: "First bill no", dataIndex: "first_bill" },
              { title: "Last bill no", dataIndex: "last_bill" }, { title: "Discount", dataIndex: "discount" }, { title: "Total", dataIndex: "total" }]} />
        </Card>
        <Typography.Paragraph type="secondary" style={{ marginTop: 12 }}>{r.note}</Typography.Paragraph>
      </>)}
    </div>
  );
}

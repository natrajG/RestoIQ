import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Card, Col, Row, Skeleton, Statistic, Typography } from "antd";
import * as echarts from "echarts/core";
import { BarChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { posApi } from "../../pos/api";

echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer]);

export function AnalyticsPage({ outletId }: { outletId: number }) {
  const summary = useQuery({ queryKey: ["analytics-summary", outletId], queryFn: () => posApi.summary(outletId) });
  const chartElement = useRef<HTMLDivElement>(null);
  const data = summary.data;
  useEffect(() => {
    const element = chartElement.current;
    if (!element || !data) return;
    const chart = echarts.init(element);
    chart.setOption({
      color: ["#6558d3"],
      tooltip: { trigger: "axis" },
      grid: { left: 18, right: 18, top: 20, bottom: 20, containLabel: true },
      xAxis: { type: "category", data: ["Actual net collections"] },
      yAxis: { type: "value", splitLine: { lineStyle: { color: "#eef0f4" } } },
      series: [{ type: "bar", data: [Number(data.net_collections_actual ?? 0)], barWidth: 52, itemStyle: { borderRadius: [8, 8, 0, 0] } }],
    });
    const resize = () => chart.resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [data]);
  return (
    <div className="page">
      <div className="page-heading"><div><Typography.Title level={2}>Sales analytics</Typography.Title><Typography.Paragraph type="secondary">Actual recorded transactions only. Opportunities are not counted as revenue.</Typography.Paragraph></div></div>
      {summary.isError && <Alert type="error" showIcon message="Sales metrics could not be loaded" />}
      {summary.isLoading ? <Skeleton active /> : (
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={8}><Card className="metric-card"><Statistic title="Gross payments (actual)" value={data?.gross_payments_actual ?? "—"} suffix={data?.currency} /></Card></Col>
          <Col xs={24} sm={8}><Card className="metric-card"><Statistic title="Refunds (actual)" value={data?.refunds_actual ?? "—"} suffix={data?.currency} /></Card></Col>
          <Col xs={24} sm={8}><Card className="metric-card"><Statistic title="Net collections (actual)" value={data?.net_collections_actual ?? "—"} suffix={data?.currency} /></Card></Col>
          <Col span={24}><Card title="Today’s recorded net collections" className="section-card"><div ref={chartElement} style={{ height: 260 }} /></Card></Col>
        </Row>
      )}
    </div>
  );
}

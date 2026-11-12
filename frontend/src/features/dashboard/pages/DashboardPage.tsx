import { useQuery } from "@tanstack/react-query";
import { Alert, Card, Col, Row, Skeleton, Statistic, Tag, Typography } from "antd";
import { ArrowUpOutlined, CameraOutlined, CheckSquareOutlined, ShopOutlined } from "@ant-design/icons";
import { posApi, type Outlet } from "../../pos/api";
import { operationsApi } from "../../ai-operations/api";

interface Props {
  outletId: number;
  outlet: Outlet;
}

export function DashboardPage({ outletId, outlet }: Props) {
  const tables = useQuery({ queryKey: ["tables", outletId], queryFn: () => posApi.tables(outletId), refetchInterval: 15000 });
  const tasks = useQuery({ queryKey: ["staff-tasks", outletId], queryFn: () => operationsApi.tasks(outletId), refetchInterval: 10000 });
  const cameras = useQuery({ queryKey: ["cameras", outletId], queryFn: () => operationsApi.cameras(outletId), refetchInterval: 30000 });
  const busy = tables.isLoading || tasks.isLoading || cameras.isLoading;
  const error = tables.error ?? tasks.error ?? cameras.error;
  const readyTables = tables.data?.filter((table) => ["FREE", "READY"].includes(table.status)).length ?? 0;
  const activeTasks = tasks.data?.length ?? 0;

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <Typography.Title level={2}>Good service starts with a clear view.</Typography.Title>
          <Typography.Paragraph type="secondary">{outlet.name} · Live operations overview</Typography.Paragraph>
        </div>
      </div>
      <Alert
        className="service-banner"
        type="success"
        showIcon
        message="Operations intelligence is active"
        description="AI table monitoring, role-based staff tasks and revenue insights run alongside your POS."
      />
      {error && <Alert type="error" showIcon message="Some live data could not be refreshed" description="Previously loaded information is retained. Check the connection and try again." />}
      {busy ? <Skeleton active /> : (
        <Row gutter={[16, 16]} className="metric-grid">
          <Col xs={24} sm={12} xl={6}>
            <Card className="metric-card"><Statistic title="Tables ready" value={readyTables} suffix={`/ ${tables.data?.length ?? 0}`} prefix={<ShopOutlined />} /></Card>
          </Col>
          <Col xs={24} sm={12} xl={6}>
            <Card className="metric-card"><Statistic title="Staff tasks" value={activeTasks} prefix={<CheckSquareOutlined />} valueStyle={{ color: activeTasks ? "#d97706" : undefined }} /></Card>
          </Col>
          <Col xs={24} sm={12} xl={6}>
            <Card className="metric-card"><Statistic title="Cameras configured" value={cameras.data?.length ?? 0} prefix={<CameraOutlined />} /></Card>
          </Col>
          <Col xs={24} sm={12} xl={6}>
            <Card className="metric-card"><Statistic title="Outlet" value={outlet.name} prefix={<ArrowUpOutlined />} /></Card>
          </Col>
        </Row>
      )}
      <Row gutter={[16, 16]} className="content-grid">
        <Col xs={24} xl={14}>
          <Card title="Floor status" extra={<Typography.Link href="/floor">View floor</Typography.Link>} className="section-card">
            {tables.isError ? <Alert type="warning" message="Floor status unavailable" /> : (
              <div className="floor-preview">
                {(tables.data ?? []).slice(0, 8).map((table) => (
                  <div className={`table-pill table-${table.status.toLowerCase()}`} key={table.id}>
                    <span>{table.name}</span><small>{table.status.toLowerCase()}</small>
                  </div>
                ))}
                {!tables.data?.length && <Typography.Text type="secondary">No tables configured for this outlet yet.</Typography.Text>}
              </div>
            )}
          </Card>
        </Col>
        <Col xs={24} xl={10}>
          <Card title="Team attention" extra={<Typography.Link href="/tasks">Open task queue</Typography.Link>} className="section-card">
            {(tasks.data ?? []).slice(0, 4).map((task) => (
              <div className="task-preview" key={task.id}>
                <span className={`task-dot task-${task.target_role}`} />
                <div><b>{task.title}</b><small>{task.target_role} team · {task.status}</small></div>
                <Tag>{task.status}</Tag>
              </div>
            ))}
            {!tasks.data?.length && !tasks.isLoading && <div className="empty-note">No open tasks. Your team is up to date.</div>}
          </Card>
        </Col>
      </Row>
      <Typography.Paragraph className="evidence-note" type="secondary">
        Camera-based detections are operational observations and remain unvalidated until evaluated against actual restaurant footage.
      </Typography.Paragraph>
    </div>
  );
}

import { CheckCircleFilled } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Progress, Skeleton, Steps, Typography } from "antd";
import { useNavigate } from "react-router-dom";
import { onboardingApi } from "../api";

export function SetupPage({ outletId }: { outletId: number }) {
  const navigate = useNavigate();
  const status = useQuery({ queryKey: ["onboarding", outletId], queryFn: () => onboardingApi.status(outletId), refetchOnWindowFocus: true });
  if (status.isLoading) return <div className="page"><Skeleton active /></div>;
  if (status.error || !status.data) return <div className="page"><Alert type="error" showIcon message="Setup status could not be loaded" /></div>;
  const s = status.data;
  const current = s.steps.findIndex((step) => !step.done);
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <Typography.Title level={2}>Set up {s.outlet}</Typography.Title>
          <Typography.Paragraph type="secondary">Complete these steps to start monitoring tables and tracking revenue. You can return here any time.</Typography.Paragraph>
        </div>
        <Progress type="circle" size={72} percent={Math.round((s.done / s.total) * 100)} />
      </div>
      {s.complete && <Alert type="success" showIcon style={{ marginBottom: 16 }} message="Setup complete" description="Your outlet is ready. Open the Live floor to watch your tables." action={<Button type="primary" onClick={() => navigate("/floor")}>Open live floor</Button>} />}
      <Card>
        <Steps direction="vertical" current={current === -1 ? s.steps.length : current}
          items={s.steps.map((step) => ({
            title: step.title,
            status: step.done ? "finish" : "process",
            icon: step.done ? <CheckCircleFilled style={{ color: "#16a34a" }} /> : undefined,
            description: (
              <div style={{ paddingBottom: 12 }}>
                <Typography.Text type="secondary">{step.detail}</Typography.Text><br />
                <Button size="small" type={step.done ? "default" : "primary"} style={{ marginTop: 8 }} onClick={() => navigate(step.route)}>{step.done ? "Review" : "Open"}</Button>
              </div>
            ),
          }))} />
      </Card>
    </div>
  );
}

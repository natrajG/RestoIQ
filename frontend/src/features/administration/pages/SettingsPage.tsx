import { useQuery } from "@tanstack/react-query";
import { Card, Space, Tag, Typography } from "antd";
import { formatInr, usePlanPrices } from "../../../shared/api/usePlanPrices";
import { adminApi } from "../api";
import type { Outlet } from "../../pos/api";

export function SettingsPage({ outlet }: { outlet: Outlet }) {
  const plans = useQuery({ queryKey: ["subscription-plans"], queryFn: adminApi.subscriptionPlans });
  const { prices } = usePlanPrices();
  const plan = plans.data?.plans.find((p) => p.name === plans.data?.current_plan) ?? plans.data?.plans[0];
  return (
    <div className="page">
      <div className="page-heading"><div><Typography.Title level={2}>Outlet settings</Typography.Title><Typography.Paragraph type="secondary">{outlet.name}</Typography.Paragraph></div></div>
      <Card title="Your subscription" className="provider-card">
        <Space direction="vertical" size={4}>
          <Typography.Text strong>RestoIQ POS <Tag color="green">CURRENT PLAN</Tag></Typography.Text>
          <Typography.Text>{plan?.entitlements.description}</Typography.Text>
          <Typography.Text type="secondary">{prices ? `${formatInr(prices.monthly)} per outlet per month or ${formatInr(prices.yearly)} per outlet per year, excluding GST.` : ""} Pay or renew from the Subscription page.</Typography.Text>
        </Space>
      </Card>
    </div>
  );
}

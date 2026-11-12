import {
  AppstoreOutlined,
  BarChartOutlined,
  CameraOutlined,
  CheckSquareOutlined,
  CoffeeOutlined,
  LogoutOutlined,
  SettingOutlined,
  TableOutlined,
  CrownOutlined,
  TeamOutlined,
  ShopOutlined,
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { Alert, Avatar, Badge, Button, Layout, Menu, notification, Select, Skeleton, Space, Tag, Typography } from "antd";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { authApi, type User } from "../../features/auth/api";
import { onboardingApi } from "../../features/onboarding/api";
import { posApi } from "../../features/pos/api";
import { operationsApi, type StaffTask } from "../../features/ai-operations/api";

import { OfflineBanner } from "../../shared/OfflineBanner";
import { clearOfflineData } from "../../shared/api/client";
import { setQueueOwner } from "../../shared/offlineQueue";
import { TaskAlerts, ALERT_ROLES } from "../../features/ai-operations/TaskAlerts";
const { Sider, Header, Content } = Layout;
const { Text } = Typography;
const DashboardPage = lazy(() => import("../../features/dashboard/pages/DashboardPage").then((module) => ({ default: module.DashboardPage })));
const FloorPage = lazy(() => import("../../features/pos/pages/FloorPage").then((module) => ({ default: module.FloorPage })));
const StaffTasksPage = lazy(() => import("../../features/ai-operations/pages/StaffTasksPage").then((module) => ({ default: module.StaffTasksPage })));
const AnalyticsPage = lazy(() => import("../../features/analytics/pages/AnalyticsPage").then((module) => ({ default: module.AnalyticsPage })));
const KitchenPage = lazy(() => import("../../features/pos/pages/KitchenPage").then((module) => ({ default: module.KitchenPage })));
const CameraPage = lazy(() => import("../../features/ai-operations/pages/CameraPage").then((module) => ({ default: module.CameraPage })));
const SettingsPage = lazy(() => import("../../features/administration/pages/SettingsPage").then((module) => ({ default: module.SettingsPage })));
const StaffPage = lazy(() => import("../../features/administration/pages/StaffPage").then((module) => ({ default: module.StaffPage })));
const PlatformAdminPage = lazy(() => import("../../features/platform-admin/pages/PlatformAdminPage").then((module) => ({ default: module.PlatformAdminPage })));
const TablesPage = lazy(() => import("../../features/administration/pages/TablesPage").then((module) => ({ default: module.TablesPage })));
const SetupPage = lazy(() => import("../../features/onboarding/pages/SetupPage").then((module) => ({ default: module.SetupPage })));
const ReportsPage = lazy(() => import("../../features/reports/pages/ReportsPage").then((module) => ({ default: module.ReportsPage })));
const MenuPage = lazy(() => import("../../features/pos/pages/MenuPage").then((module) => ({ default: module.MenuPage })));
const OrdersPage = lazy(() => import("../../features/pos/pages/OrdersPage").then((module) => ({ default: module.OrdersPage })));
const ExceptionsPage = lazy(() => import("../../features/pos/pages/ExceptionsPage").then((module) => ({ default: module.ExceptionsPage })));
const SalesSummaryPage = lazy(() => import("../../features/pos/pages/SalesSummaryPage").then((module) => ({ default: module.SalesSummaryPage })));
const GstReportPage = lazy(() => import("../../features/pos/pages/GstReportPage").then((module) => ({ default: module.GstReportPage })));
const CustomersPage = lazy(() => import("../../features/pos/pages/CustomersPage").then((module) => ({ default: module.CustomersPage })));
const DayClosePage = lazy(() => import("../../features/pos/pages/DayClosePage").then((module) => ({ default: module.DayClosePage })));
const IntegrationsPage = lazy(() => import("../../features/integrations/IntegrationsPage").then((module) => ({ default: module.IntegrationsPage })));
const BillingPage = lazy(() => import("../../features/billing/pages/BillingPage").then((module) => ({ default: module.BillingPage })));
const NativePosPage = lazy(() => import("../../features/pos/pages/NativePosPage").then((module) => ({ default: module.NativePosPage })));

interface Props {
  user: User;
  onLogout: () => void;
}

export function AppShell({ user, onLogout }: Props) {
  setQueueOwner(user.tenant_id);
  const location = useLocation();
  const navigate = useNavigate();
  const outlets = useQuery({ queryKey: ["outlets"], queryFn: posApi.outlets });
  const [selectedOutletId, setSelectedOutletId] = useState<number | undefined>(
    () => Number(sessionStorage.getItem("outletId")) || undefined,
  );
  const taskOutletId = outlets.data?.find((item) => item.id === selectedOutletId)?.id ?? outlets.data?.[0]?.id;
  const tasks = useQuery({
    queryKey: ["staff-tasks", taskOutletId],
    queryFn: () => taskOutletId === undefined ? Promise.resolve([] as StaffTask[]) : operationsApi.tasks(taskOutletId),
    enabled: taskOutletId !== undefined,
    refetchInterval: 10000,
  });
  const canSetup = ["owner", "admin", "manager"].includes(user.role.toLowerCase());
  const setup = useQuery({
    queryKey: ["onboarding", taskOutletId],
    queryFn: () => onboardingApi.status(taskOutletId as number),
    enabled: canSetup && taskOutletId !== undefined,
  });
  const [setupShown, setSetupShown] = useState(() => sessionStorage.getItem("setupShown") === "1");
  const needsSetup = canSetup && setup.data?.complete === false && !setupShown;
  useEffect(() => {
    if (needsSetup) { sessionStorage.setItem("setupShown", "1"); setSetupShown(true); }
  }, [needsSetup]);
  const knownTaskIds = useRef<Set<number> | null>(null);
  const knownTaskOutlet = useRef<number | undefined>(undefined);
  useEffect(() => {
    if (!tasks.data || taskOutletId === undefined) return;
    if (knownTaskOutlet.current !== taskOutletId) {
      knownTaskOutlet.current = taskOutletId;
      knownTaskIds.current = new Set(tasks.data.map((task) => task.id));
      return;
    }
    const previous = knownTaskIds.current;
    const added = previous ? tasks.data.filter((task) => !previous.has(task.id)) : [];
    if (added.length) {
      notification.info({
        message: "New staff task",
        description: added.length === 1 ? added[0].title : `${added.length} new tasks are waiting for your team.`,
        placement: "topRight",
      });
    }
    knownTaskIds.current = new Set(tasks.data.map((task) => task.id));
  }, [tasks.data, taskOutletId]);
  const role = user.role.toLowerCase();
  const entries = useMemo(() => {
    const all = [
      { key: "/platform", label: "Platform admin", icon: <CrownOutlined />, roles: ["platform_admin"] },
      { key: "/setup", label: "Setup guide", icon: <CheckSquareOutlined />, roles: ["owner", "admin", "manager"] },
      { key: "/", label: "Overview", icon: <AppstoreOutlined />, roles: ["owner", "admin", "platform_admin", "manager", "analyst"] },
      { key: "/pos", label: "Native POS", icon: <CoffeeOutlined />, roles: ["owner", "admin", "manager", "waiter", "server", "cashier"] },
      { key: "/floor", label: "Live floor", icon: <ShopOutlined />, roles: ["owner", "admin", "manager", "waiter", "server", "cleaner", "cleaning"] },
      { key: "/tasks", label: "Staff tasks", icon: <CheckSquareOutlined />, roles: ["owner", "admin", "manager", "waiter", "server", "cleaner", "cleaning", "kitchen", "cashier"] },
      { key: "/orders", label: "Orders & billing", icon: <ShopOutlined />, roles: ["owner", "admin", "manager", "waiter", "server", "cashier"] },
      { key: "/integrations", label: "Integrations", icon: <SettingOutlined />, roles: ["owner", "admin"] },
      { key: "/customers", label: "Customers", icon: <TeamOutlined />, roles: ["owner", "admin", "manager", "cashier", "waiter", "server"] },
      { key: "/day-close", label: "Day close & cash", icon: <BarChartOutlined />, roles: ["owner", "admin", "manager", "cashier"] },
      { key: "/sales-summary", label: "Sales summary", icon: <BarChartOutlined />, roles: ["owner", "admin", "manager", "cashier", "analyst"] },
      { key: "/exceptions", label: "Exceptions", icon: <BarChartOutlined />, roles: ["owner", "admin", "manager"] },
      { key: "/gst-report", label: "GST report", icon: <BarChartOutlined />, roles: ["owner", "admin", "manager", "cashier"] },
      { key: "/kitchen", label: "Kitchen", icon: <CoffeeOutlined />, roles: ["owner", "admin", "manager", "kitchen", "waiter", "server"] },
      { key: "/menu", label: "Menu & GST", icon: <ShopOutlined />, roles: ["owner", "admin", "manager"] },
      { key: "/reports", label: "Reports", icon: <BarChartOutlined />, roles: ["owner", "admin", "manager", "analyst"] },
      { key: "/analytics", label: "Sales analytics", icon: <BarChartOutlined />, roles: ["owner", "admin", "manager", "analyst"] },
      { key: "/cameras", label: "AI monitoring", icon: <CameraOutlined />, roles: ["owner", "admin", "manager"] },
      { key: "/tables", label: "Tables & floor", icon: <TableOutlined />, roles: ["owner", "admin", "manager"] },
      { key: "/staff", label: "Staff & access", icon: <TeamOutlined />, roles: ["owner", "admin", "manager"] },
      { key: "/billing", label: "Subscription", icon: <CrownOutlined />, roles: ["owner"] },
      { key: "/settings", label: "Settings", icon: <SettingOutlined />, roles: ["owner", "admin", "manager"] },
    ];
    return all.filter((item) => (role === "platform_admin" ? item.key === "/platform" : item.roles.includes(role)));
  }, [role]);
  const menuItems = entries.map(({ key, label, icon }) => ({
    key,
    label: key === "/tasks"
      ? <span>Staff tasks <Badge count={tasks.data?.length ?? 0} size="small" /></span>
      : label,
    icon,
  }));

  async function logout() {
    try {
      await authApi.logout();
    } finally {
      clearOfflineData();
      onLogout();
      navigate("/");
    }
  }

  if (user.subscription?.locked) {
    return (
      <div style={{ padding: 24, maxWidth: 800, margin: "0 auto" }}>
        {user.role === "owner" ? (
          <Suspense fallback={null}><BillingPage locked /></Suspense>
        ) : (
          <Alert type="warning" showIcon message="Your free trial has ended"
            description="Ask the restaurant owner to renew the RestoIQ plan. Your data is safe and access resumes as soon as it is active." />
        )}
        <Button style={{ marginTop: 16 }} onClick={() => void logout()}>Sign out</Button>
      </div>
    );
  }
  if (outlets.isLoading) return <div className="boot-screen"><span>Loading your workspace…</span></div>;
  if (outlets.isError) {
    return <div className="boot-screen"><Alert type="error" showIcon message="Could not load outlets" description="Refresh the page or contact your administrator." /></div>;
  }
  if (!outlets.data?.length) {
    return <div className="boot-screen"><Alert type="info" showIcon message="No outlet access" description="Ask your organization owner to assign an outlet." /></div>;
  }
  const activeOutlet = outlets.data.find((item) => item.id === selectedOutletId) ?? outlets.data[0];
  const activeOutletId = activeOutlet.id;

  return (
    <Layout className="app-layout">
      <Sider breakpoint="lg" collapsedWidth="0" width={252} className="app-sider">
        <Link to="/" className="brand" style={{ height: "auto", padding: 0 }}>
          <span className="brand-logo"><img src="/images/logo.png" alt="RestoIQ" /></span>
        </Link>
        <div className="workspace-label">WORKSPACE</div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[entries.find((item) => item.key !== "/" && location.pathname.startsWith(item.key))?.key ?? "/"]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
        <div className="sider-footer">
          <div className="sider-status-dot" />
          <span>Operations online</span>
        </div>
      </Sider>
      <Layout>
        <Header className="app-header">
          <Space size="middle">
            <Select
              aria-label="Select outlet"
              value={activeOutletId}
              options={outlets.data.map((item) => ({ value: item.id, label: item.name }))}
              onChange={(value) => {
                sessionStorage.setItem("outletId", String(value));
                setSelectedOutletId(value);
              }}
              style={{ minWidth: 190 }}
            />
            <Tag color="blue">RESTOIQ POS</Tag>
          </Space>
          <Space size="middle">
            <div className="user-chip"><Avatar size="small">{user.email.slice(0, 1).toUpperCase()}</Avatar><Text>{user.email}</Text></div>
            <Button type="text" icon={<LogoutOutlined />} onClick={() => void logout()} aria-label="Log out" />
          </Space>
        </Header>
        <Content className="app-content">
          <OfflineBanner />
          {ALERT_ROLES.includes(role) && <TaskAlerts outletId={activeOutletId} openTo={role === "kitchen" ? "/kitchen" : "/tasks"} />}
          {user.role === "owner" && user.subscription && (user.subscription.status === "grace" || (user.subscription.status === "active" && user.subscription.days_left !== null && user.subscription.days_left <= 7)) && (
            <Alert style={{ marginBottom: 16 }} type="warning" showIcon
              message={user.subscription.status === "grace" ? "Your plan has ended. Renew now to avoid losing access in a few days." : `Your plan renews in ${user.subscription.days_left} day(s)`}
              action={<Button size="small" type="primary" onClick={() => navigate("/billing")}>Renew</Button>} />
          )}
          {user.subscription?.status === "trial" && user.subscription.days_left !== null && (
            <Alert style={{ marginBottom: 16 }} type={user.subscription.days_left <= 5 ? "warning" : "info"} showIcon
              message={`Free trial: ${user.subscription.days_left} day${user.subscription.days_left === 1 ? "" : "s"} left`} />
          )}
          <Suspense fallback={<Skeleton active />}>
            <Routes>
              <Route path="/" element={role === "platform_admin" ? <Navigate to="/platform" replace /> : needsSetup ? <Navigate to="/setup" replace /> : entries.some((item) => item.key === "/") ? <DashboardPage outletId={activeOutletId} outlet={activeOutlet} /> : <Navigate to={entries[0]?.key ?? "/floor"} replace />} />
              <Route path="/billing" element={<BillingPage />} />
              <Route path="/setup" element={<SetupPage outletId={activeOutletId} />} />
              <Route path="/pos" element={<NativePosPage outletId={activeOutletId} outlet={activeOutlet} />} />
              <Route path="/floor" element={<FloorPage outletId={activeOutletId} />} />
              <Route path="/tasks" element={<StaffTasksPage outletId={activeOutletId} />} />
              <Route path="/menu" element={<MenuPage outletId={activeOutletId} currency={activeOutlet?.currency ?? "INR"} />} />
              <Route path="/reports" element={<ReportsPage outletId={activeOutletId} />} />
              <Route path="/analytics" element={<AnalyticsPage outletId={activeOutletId} />} />
              <Route path="/orders" element={<OrdersPage outletId={activeOutletId} currency={activeOutlet?.currency ?? "INR"} restaurantName={activeOutlet?.name} />} />
              <Route path="/integrations" element={<IntegrationsPage outletId={activeOutletId} />} />
              <Route path="/customers" element={<CustomersPage outletId={activeOutletId} />} />
              <Route path="/day-close" element={<DayClosePage outletId={activeOutletId} currency={activeOutlet?.currency ?? "INR"} canDelete={["owner", "admin", "manager"].includes(role)} />} />
              <Route path="/exceptions" element={<ExceptionsPage outletId={activeOutletId} currency={activeOutlet?.currency ?? "INR"} />} />
              <Route path="/sales-summary" element={<SalesSummaryPage outletId={activeOutletId} currency={activeOutlet?.currency ?? "INR"} />} />
              <Route path="/gst-report" element={<GstReportPage outletId={activeOutletId} currency={activeOutlet?.currency ?? "INR"} />} />
              <Route path="/kitchen" element={<KitchenPage outletId={activeOutletId} restaurantName={activeOutlet?.name} />} />
              <Route path="/cameras" element={<CameraPage outletId={activeOutletId} />} />
              {role === "platform_admin" && <Route path="/platform" element={<PlatformAdminPage />} />}
              <Route path="/tables" element={<TablesPage outlet={activeOutlet} />} />
              <Route path="/staff" element={<StaffPage outlets={outlets.data} canAssignManagers={["owner", "admin", "platform_admin"].includes(role)} />} />
              <Route path="/settings" element={<SettingsPage outlet={activeOutlet} />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </Content>
      </Layout>
    </Layout>
  );
}

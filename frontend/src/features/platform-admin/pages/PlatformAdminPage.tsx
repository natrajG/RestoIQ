import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, InputNumber, Popconfirm, Segmented, Statistic, Steps, Table, Tabs, Tag, Typography, message } from "antd";
import { useState } from "react";
import { platformApi, type PlanPrice, type PlatformInvoice, type PlatformRestaurant, type ReminderEntry } from "../api";

const inr = (n: number) => `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
const planLabel = (_n: string) => "RestoIQ POS";
const statusColor: Record<string, string> = { trial: "gold", active: "green", paid: "green", pending: "orange", void: "default", grace: "orange", expired: "red", sent: "green", failed: "red", not_configured: "default" };
const statusLabel: Record<string, string> = { trial: "Free trial", active: "Paid", grace: "Overdue", expired: "Expired", none: "—" };
const dateTime = (v: string | null) => (v ? new Date(v).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "—");
const date = (v: string | null) => (v ? new Date(v).toLocaleDateString("en-IN") : "—");

const ONBOARDING_STEPS: [string, string][] = [
  ["1. Restaurant signs up", "Self-serve on the website: owner, restaurant, address, GSTIN (optional), password. A 30-day free trial starts and a welcome email is sent."],
  ["2. Set up menu and GST", "Owner opens Menu & GST: add categories and items, or import an Excel/CSV file. Choose the GST scheme."],
  ["3. Tables, staff and printing", "Add floors and tables, create staff logins (manager, cashier, waiter, kitchen) and connect a receipt/KOT printer."],
  ["4. Cameras (optional)", "Add CCTV streams under AI monitoring and map them to tables for live table status."],
  ["5. Test order and go-live", "Place a test dine-in order, send to kitchen, take a payment and print the bill, then train the staff."],
  ["6. Before the trial ends", "The owner opens Subscription and chooses \"Subscribe with auto-renew\" (recommended) or \"Pay once\". Nothing is charged until the trial ends. You can also create an invoice, mark it paid or extend the trial from the Restaurants tab."],
  ["7. Renewal", "Auto-renew customers are charged automatically by Razorpay and receive a receipt. Others get reminder emails 7, 3 and 1 day before expiry; after a 3-day grace period the account locks until payment."],
  ["8. Price changes", "A new price applies to new subscriptions. Existing auto-renew customers keep their locked amount until they cancel and re-subscribe; adding an outlet also needs a re-subscribe."],
];

function PlanRow({ plan }: { plan: PlanPrice }) {
  const queryClient = useQueryClient();
  const [price, setPrice] = useState(plan.price_inr);
  const [yearly, setYearly] = useState(plan.yearly_price_inr);
  const [gst, setGst] = useState(plan.gst_percent);
  const save = useMutation({
    mutationFn: () => platformApi.updatePlan(plan.plan_name, { price_inr: price, yearly_price_inr: yearly, gst_percent: gst }),
    onSuccess: () => { message.success("Pricing updated"); void queryClient.invalidateQueries({ queryKey: ["platform-plans"] }); },
    onError: (e: Error) => message.error(e.message),
  });
  return (
    <Card className="section-card" title="Subscription price (per outlet)">
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "end" }}>
        <label>Price per outlet / month (₹)<br /><InputNumber min={0} value={price} onChange={(v) => setPrice(v ?? 0)} style={{ width: 180 }} /></label>
        <label>Price per outlet / year (₹)<br /><InputNumber min={0} value={yearly} onChange={(v) => setYearly(v ?? 0)} style={{ width: 180 }} /></label>
        <label>GST %<br /><InputNumber min={0} max={100} value={gst} onChange={(v) => setGst(v ?? 0)} style={{ width: 120 }} /></label>
        <Button type="primary" loading={save.isPending} onClick={() => save.mutate()}>Save</Button>
      </div>
      <Typography.Paragraph type="secondary" style={{ marginTop: 12 }}>
        Saved changes apply to new invoices only. Pending invoices keep their old price, The landing page, signup and legal pages show this price.
      </Typography.Paragraph>
    </Card>
  );
}

export function PlatformAdminPage() {
  const queryClient = useQueryClient();
  const restaurants = useQuery({ queryKey: ["platform-restaurants"], queryFn: platformApi.restaurants });
  const invoices = useQuery({ queryKey: ["platform-invoices"], queryFn: platformApi.invoices });
  const plans = useQuery({ queryKey: ["platform-plans"], queryFn: platformApi.plans });
  const reminders = useQuery({ queryKey: ["platform-reminders"], queryFn: platformApi.reminders });
  const [filter, setFilter] = useState("all");
  const remind = useMutation({
    mutationFn: platformApi.remind,
    onSuccess: (r) => { message.success(`Reminder emailed to ${r.sent_to}`); void queryClient.invalidateQueries({ queryKey: ["platform-reminders"] }); refresh(); },
    onError: (e: Error) => { message.error(e.message); void queryClient.invalidateQueries({ queryKey: ["platform-reminders"] }); },
  });
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["platform-invoices"] });
    void queryClient.invalidateQueries({ queryKey: ["platform-restaurants"] });
  };
  const create = useMutation({
    mutationFn: platformApi.createInvoice,
    onSuccess: (inv) => { message.success(`Invoice ${inv.number} created`); refresh(); },
    onError: (e: Error) => message.error(e.message),
  });
  const subscription = useMutation({
    mutationFn: ({ id, action }: { id: number; action: "extend_trial" | "activate" }) => platformApi.changeSubscription(id, action),
    onSuccess: () => { message.success("Subscription updated"); refresh(); },
    onError: (e: Error) => message.error(e.message),
  });
  const setStatus = useMutation({
    mutationFn: ({ inv, status }: { inv: PlatformInvoice; status: string }) => platformApi.setInvoiceStatus(inv, status),
    onSuccess: refresh,
    onError: (e: Error) => message.error(e.message),
  });
  const all = restaurants.data?.restaurants ?? [];
  const count = (st: string[]) => all.filter((r) => st.includes(r.subscription_status)).length;
  const rows = filter === "all" ? all : all.filter((r) => (filter === "overdue" ? ["grace", "expired"] : [filter]).includes(r.subscription_status));

  return (
    <div className="page">
      <div className="page-heading"><div><Typography.Title level={2}>Platform admin</Typography.Title>
        <Typography.Paragraph type="secondary">Restaurants using RestoIQ, their payments and renewal reminders.</Typography.Paragraph></div></div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: 16, marginBottom: 16 }}>
        <Card><Statistic title="Restaurants" value={all.length} /></Card>
        <Card><Statistic title="Paying" value={count(["active"])} /></Card>
        <Card><Statistic title="On free trial" value={count(["trial"])} /></Card>
        <Card><Statistic title="Overdue / expired" value={count(["grace", "expired"])} valueStyle={count(["grace", "expired"]) ? { color: "#cf1322" } : undefined} /></Card>
        <Card><Statistic title="Collected" value={inr(invoices.data?.totals.paid ?? 0)} /></Card>
        <Card><Statistic title="Payment due" value={inr(invoices.data?.totals.pending ?? 0)} /></Card>
      </div>
      <Tabs defaultActiveKey="plans" items={[
        { key: "plans", label: "Plans & pricing", children: (
          <div style={{ display: "grid", gap: 16 }}>{(plans.data?.plans ?? []).map((p) => <PlanRow key={`${p.plan_name}-${p.price_inr}-${p.yearly_price_inr}-${p.gst_percent}`} plan={p} />)}</div>
        ) },
        { key: "reminders", label: "Reminder log", children: (
          <Table<ReminderEntry> rowKey="id" loading={reminders.isLoading} dataSource={reminders.data?.reminders ?? []} pagination={{ pageSize: 10 }} scroll={{ x: true }}
            locale={{ emptyText: "No reminders sent yet. They go out automatically 7, 3 and 1 day before a plan ends." }}
            columns={[
              { title: "When", dataIndex: "created_at", render: dateTime },
              { title: "Restaurant", dataIndex: "restaurant" },
              { title: "Sent to", dataIndex: "to_email" },
              { title: "Type", dataIndex: "kind", render: (k: string) => (k === "auto" ? "Automatic" : "Manual") },
              { title: "Days left", dataIndex: "days_left", render: (d: number | null) => d ?? "—" },
              { title: "Result", dataIndex: "status", render: (st: string) => <Tag color={statusColor[st]}>{st === "not_configured" ? "email not set up" : st}</Tag> },
            ]} />
        ) },
        { key: "onboarding", label: "Onboarding steps", children: (
          <Card className="section-card" title="Onboarding a new restaurant">
            <Steps direction="vertical" size="small" items={ONBOARDING_STEPS.map(([title, description]) => ({ title, description, status: "process" as const }))} />
          </Card>
        ) },
        { key: "restaurants", label: `Restaurants (${all.length})`, children: (
          <>
            <Segmented style={{ marginBottom: 12 }} value={filter} onChange={(v) => setFilter(String(v))} options={[
              { label: `All (${all.length})`, value: "all" }, { label: `Paying (${count(["active"])})`, value: "active" },
              { label: `Trial (${count(["trial"])})`, value: "trial" }, { label: `Overdue (${count(["grace", "expired"])})`, value: "overdue" }]} />
            <Table<PlatformRestaurant> rowKey="id" loading={restaurants.isLoading} dataSource={rows} pagination={{ pageSize: 10 }} scroll={{ x: true }}
              columns={[
                { title: "Restaurant", render: (_, r) => <div><b>{r.name}</b><br /><small>{r.city ?? ""} · joined {date(r.created_at)}</small></div> },
                { title: "Owner", render: (_, r) => <div>{r.owner_name ?? "—"}<br /><small>{r.owner_email}{r.mobile ? ` · ${r.mobile}` : ""}</small></div> },
                { title: "Status", render: (_, r) => <div><Tag color={statusColor[r.subscription_status]}>{statusLabel[r.subscription_status] ?? r.subscription_status}</Tag><br />
                  <small>{r.subscription_status === "expired" ? `ended ${date(r.plan_ends_at)}` : r.plan_ends_at ? `${["trial"].includes(r.subscription_status) ? "trial ends" : "paid until"} ${date(r.plan_ends_at)}${r.days_left !== null ? ` (${r.days_left}d)` : ""}` : ""}</small></div> },
                { title: "Outlets", dataIndex: "outlets" },
                { title: "Paid", render: (_, r) => <div>{inr(r.paid_total)}<br /><small>{r.last_paid_at ? `last ${date(r.last_paid_at)}` : "no payment yet"}</small></div> },
                { title: "Due", dataIndex: "amount_due", render: (v: number) => (v > 0 ? <b style={{ color: "#cf1322" }}>{inr(v)}</b> : "—") },
                { title: "Reminders", render: (_, r) => <div>{r.reminders_sent}<br /><small>{r.last_reminder_at ? `last ${date(r.last_reminder_at)}` : "none sent"}</small></div> },
                { title: "", render: (_, r) => (
                  <span style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <Button size="small" loading={remind.isPending && remind.variables === r.id} onClick={() => remind.mutate(r.id)}>Send reminder</Button>
                    {r.subscription_status !== "trial" && <Button size="small" loading={create.isPending && create.variables === r.id} onClick={() => create.mutate(r.id)}>Create invoice</Button>}
                    {["trial", "grace", "expired"].includes(r.subscription_status) && <Button size="small" onClick={() => subscription.mutate({ id: r.id, action: "extend_trial" })}>+7 days</Button>}
                  </span>) },
              ]} />
          </>
        ) },
        { key: "invoices", label: "Invoices", children: (
          <Table<PlatformInvoice> rowKey="id" loading={invoices.isLoading} dataSource={invoices.data?.invoices ?? []} pagination={{ pageSize: 10 }} scroll={{ x: true }}
            locale={{ emptyText: "No invoices yet. They appear when a restaurant starts to pay." }}
            columns={[
              { title: "Invoice", dataIndex: "number" },
              { title: "Restaurant", dataIndex: "tenant_name" },
              { title: "Plan", dataIndex: "plan_name", render: (p: string) => planLabel(p) },
              { title: "Period", render: (_, i) => `${date(i.period_start)} – ${date(i.period_end)}` },
              { title: "Outlets", dataIndex: "outlets" },
              { title: "Subtotal", dataIndex: "subtotal", render: inr },
              { title: "GST", dataIndex: "gst", render: inr },
              { title: "Total", dataIndex: "total", render: (v: number) => <b>{inr(v)}</b> },
              { title: "Status", dataIndex: "status", render: (s: string) => <Tag color={statusColor[s]}>{s}</Tag> },
              { title: "", render: (_, i) => i.status === "pending" && (
                <span style={{ display: "flex", gap: 8 }}>
                  <Button size="small" type="primary" onClick={() => setStatus.mutate({ inv: i, status: "paid" })}>Mark paid</Button>
                  <Popconfirm title="Void this invoice?" onConfirm={() => setStatus.mutate({ inv: i, status: "void" })}><Button size="small" danger>Void</Button></Popconfirm>
                </span>) },
            ]} />
        ) },
      ]} />
    </div>
  );
}

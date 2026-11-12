import { useState } from "react";
import { Alert, Button, Card, Popconfirm, Radio, Space, Table, Tag, Typography, message } from "antd";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { printTaxInvoice } from "../printInvoice";
import { billingApi, loadCheckout, type AutoRenewResponse, type AutoRenewStart, type BillingInvoice, type Checkout, type RazorpayResponse } from "../api";

const { Title, Text } = Typography;
const rupees = (value: number) => `₹${value.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const day = (value: string) => new Date(value).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });

export function BillingPage({ locked = false }: { locked?: boolean }) {
  const queryClient = useQueryClient();
  const status = useQuery({ queryKey: ["billing"], queryFn: billingApi.status });
  const [cycle, setCycle] = useState<"monthly" | "yearly">("yearly");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [paid, setPaid] = useState(false);

  async function pay() {
    setBusy(true);
    setError(undefined);
    try {
      const [order] = await Promise.all([billingApi.checkout(cycle), loadCheckout()]);
      await open(order);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Payment could not be started");
      setBusy(false);
    }
  }

  async function startAutoRenew() {
    setBusy(true);
    setError(undefined);
    try {
      const [s] = await Promise.all([billingApi.startAutoRenew(cycle), loadCheckout()]);
      await openAuto(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Auto-renew could not be started");
      setBusy(false);
    }
  }

  function openAuto(s: AutoRenewStart) {
    return new Promise<void>((resolve) => {
      const checkout = new window.Razorpay!({
        key: s.key_id, subscription_id: s.subscription_id, name: "RestoIQ", description: s.description, prefill: { email: s.email ?? undefined }, theme: { color: "#c2410c" },
        modal: { ondismiss: () => { setBusy(false); resolve(); } },
        handler: async (response: AutoRenewResponse) => {
          try {
            await billingApi.verifyAutoRenew(response);
            message.success("Auto-renew is on");
            await queryClient.invalidateQueries();
            if (locked) window.location.reload();
          } catch (e) {
            setError(`${e instanceof Error ? e.message : "Could not confirm"} If you approved the payment, auto-renew switches on automatically within a few minutes.`);
          } finally { setBusy(false); resolve(); }
        },
      });
      checkout.on("payment.failed", () => setError("The authorisation failed. You were not charged; please try again."));
      checkout.open();
    });
  }

  async function stopAutoRenew() {
    try {
      await billingApi.cancelAutoRenew();
      message.success("Auto-renew cancelled. Your plan stays active until its end date.");
      await queryClient.invalidateQueries();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not cancel"); }
  }

  function open(order: Checkout) {
    return new Promise<void>((resolve) => {
      const checkout = new window.Razorpay!({
        key: order.key_id,
        order_id: order.razorpay_order_id,
        amount: order.amount,
        currency: order.currency,
        name: "RestoIQ",
        description: order.description,
        prefill: { email: order.email ?? undefined },
        theme: { color: "#c2410c" },
        modal: { ondismiss: () => { setBusy(false); resolve(); } },
        handler: async (response: RazorpayResponse) => {
          try {
            await billingApi.verify(response);
            setPaid(true);
            message.success("Payment received. Thank you!");
            await queryClient.invalidateQueries();
            // The workspace reloads so a locked account opens straight away
            if (locked) window.location.reload();
          } catch (e) {
            setError(`${e instanceof Error ? e.message : "Could not confirm the payment"} If money was deducted, your plan is activated automatically within a few minutes.`);
          } finally {
            setBusy(false);
            resolve();
          }
        },
      });
      checkout.on("payment.failed", () => setError("The payment failed. You were not charged; please try again."));
      checkout.open();
    });
  }

  const data = status.data;
  const price = data?.price;
  const gst = price?.gst_percent ?? 18;
  const amount = price ? (cycle === "yearly" ? price.yearly : price.monthly) : 0;
  const total = amount * (1 + gst / 100);
  const sub = data?.subscription;
  const auto = data?.autorenew;
  const autoOn = auto && ["authenticated", "active"].includes(auto.status);

  return (
    <div className="page" style={{ maxWidth: 760 }}>
      <Title level={3}>Subscription &amp; billing</Title>
      {sub && (
        <Alert
          style={{ marginBottom: 16 }}
          showIcon
          type={sub.locked ? "warning" : "info"}
          message={sub.locked ? "Your free trial has ended"
            : sub.status === "trial" ? `Free trial: ${sub.days_left ?? 0} day(s) left`
            : sub.status === "active" ? `Plan active until ${sub.trial_ends_at ? day(sub.trial_ends_at) : "-"}` : `Plan status: ${sub.status}`}
          description={sub.locked ? "Pay below to continue. Your data is safe and access resumes straight after payment."
            : sub.status === "trial" ? "Pay now if you like: your paid period starts after the trial ends, so no trial day is lost." : undefined}
        />
      )}
      {paid && <Alert style={{ marginBottom: 16 }} type="success" showIcon message="Payment received. Your plan is active." />}
      {error && <Alert style={{ marginBottom: 16 }} type="error" showIcon message={error} />}
      <Card title="RestoIQ POS plan">
        {data && !data.payments_enabled && <Alert type="warning" showIcon style={{ marginBottom: 12 }} message="Online payment is not switched on yet. Please contact RestoIQ support." />}
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Radio.Group value={cycle} onChange={(e) => setCycle(e.target.value)} optionType="button" buttonStyle="solid">
            <Radio.Button value="yearly">Yearly {price ? rupees(price.yearly) : ""}</Radio.Button>
            <Radio.Button value="monthly">Monthly {price ? rupees(price.monthly) : ""}</Radio.Button>
          </Radio.Group>
          <Text type="secondary">Price is per outlet. Includes POS billing, GST invoices, kitchen, offline mode, table monitoring and reports.</Text>
          <Text>{rupees(amount)} + {gst}% GST = <strong>{rupees(total)}</strong> per outlet</Text>
          {autoOn ? (
            <Alert type="success" showIcon message={`Auto-renew is on: ${rupees(auto.amount)} (incl. GST) every ${auto.billing_cycle === "yearly" ? "year" : "month"}`}
              description="The first charge happens when your free trial or current period ends. You get an email receipt each time."
              action={<Popconfirm title="Stop auto-renew? Your plan stays active until its end date." onConfirm={() => void stopAutoRenew()}><Button size="small" danger>Cancel auto-renew</Button></Popconfirm>} />
          ) : (
            <>
              {auto?.status === "halted" && <Alert type="error" showIcon message="Your last automatic payment failed. Set up auto-renew again or pay once below." />}
              <Button type="primary" size="large" loading={busy} disabled={!data?.payments_enabled} onClick={() => void startAutoRenew()}>
                Subscribe with auto-renew (recommended)
              </Button>
              <Text type="secondary" style={{ fontSize: 12 }}>Your UPI AutoPay, card or netbanking mandate is charged {cycle === "yearly" ? "once a year" : "monthly"}. The price is locked at today's rate until you cancel; cancel any time here.</Text>
              <Button loading={busy} disabled={!data?.payments_enabled} onClick={() => void pay()}>
                Pay once with Razorpay (no auto-renew)
              </Button>
            </>)}
          <Text type="secondary" style={{ fontSize: 12 }}>UPI, cards, netbanking and wallets accepted. Payments are processed by Razorpay; we never see your card details.</Text>
        </Space>
      </Card>
      {!locked && (
        <Card title="Payment history" style={{ marginTop: 16 }}>
          <Table<BillingInvoice> size="small" rowKey="id" pagination={false} dataSource={data?.invoices ?? []} loading={status.isLoading}
            locale={{ emptyText: "No payments yet" }}
            columns={[
              { title: "Invoice", dataIndex: "number" },
              { title: "Period", render: (_, r) => `${day(r.period_start)} – ${day(r.period_end)}` },
              { title: "Outlets", dataIndex: "outlets" },
              { title: "Total", align: "right", render: (_, r) => rupees(r.total) },
              { title: "Status", render: (_, r) => <Tag color={r.status === "paid" ? "green" : r.status === "void" ? "default" : "orange"}>{r.status}</Tag> },
              { title: "", render: (_, r) => r.status === "paid" ? <Button size="small" onClick={() => void billingApi.taxInvoice(r.id).then(printTaxInvoice).catch(() => message.error("Could not load the invoice"))}>Invoice</Button> : null },
            ]} />
        </Card>
      )}
    </div>
  );
}

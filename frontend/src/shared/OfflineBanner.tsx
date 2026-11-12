import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Alert, Button, Form, Input, InputNumber, Modal, Select, message } from "antd";
import { printProvisional } from "../features/pos/printing";
import { addOfflinePayment, discardQueued, syncQueue, useOnline, useQueue, type QueuedOrder } from "./offlineQueue";

export function OfflineBanner() {
  const online = useOnline();
  const queue = useQueue();
  const client = useQueryClient();
  const pending = queue.filter((q) => !q.error);
  const failed = queue.filter((q) => q.error);
  const [payFor, setPayFor] = useState<QueuedOrder | null>(null);
  const [form] = Form.useForm();
  const payable = (q: QueuedOrder) => (q.charges?.total ?? 0) / 100;
  const received = (q: QueuedOrder) => (q.payments ?? []).reduce((t, p) => t + Number(p.amount), 0);

  useEffect(() => {
    if (!online || !pending.length) return;
    const run = async () => {
      const sent = await syncQueue();
      if (sent) {
        message.success(`${sent} offline order${sent > 1 ? "s" : ""} sent to the kitchen`);
        void client.invalidateQueries();
      }
    };
    void run();
    const t = setInterval(() => void run(), 15000);
    return () => clearInterval(t);
  }, [online, pending.length, client]);

  return (
    <>
      {!online && <Alert style={{ marginBottom: 12 }} type="warning" showIcon
        message={`You are offline. Orders are safe on this device${pending.length ? ` (${pending.length} waiting to send)` : ""} and are sent automatically when the internet is back. Payments, bills and other screens need internet.`} />}
      {online && pending.length > 0 && <Alert style={{ marginBottom: 12 }} type="info" showIcon message={`Sending ${pending.length} saved order${pending.length > 1 ? "s" : ""} to the kitchen…`} />}
      {pending.map((q) => (
        <Alert key={q.key} style={{ marginBottom: 12 }} type="info" showIcon
          message={`${q.orderId ? "✓ Sent to kitchen" : online ? "⏳ Sending" : "⏳ Waiting for internet"}: ${q.label}${q.charges ? ` · total ${(q.charges.total / 100).toFixed(2)}` : ""}${received(q) ? ` · received ${received(q).toFixed(2)}` : ""}`}
          description={q.orderId ? "Payment will be recorded once the order is marked handed over / delivered." : undefined}
          action={q.charges && (
            <>
              <Button size="small" onClick={() => printProvisional(q, "INR")}>Provisional bill</Button>{" "}
              {received(q) < payable(q) && <Button size="small" type="primary" onClick={() => { setPayFor(q); form.setFieldsValue({ method: "cash", amount: payable(q) - received(q), reference: "" }); }}>Payment received</Button>}
            </>)} />
      ))}
      <Modal open={!!payFor} title="Record payment received (saved offline)" okText="Save" onCancel={() => setPayFor(null)} onOk={() => form.submit()} destroyOnClose>
        <Form form={form} layout="vertical" onFinish={(v: { method: string; amount: number; reference?: string }) => {
          if (payFor) addOfflinePayment(payFor.key, { method: v.method, amount: v.amount.toFixed(2), reference: v.reference || undefined });
          setPayFor(null);
        }}>
          <Form.Item name="method" label="Method"><Select options={[{ value: "cash", label: "Cash" }, { value: "upi_external", label: "UPI (customer's own app)" }, { value: "card_external", label: "Card machine" }]} /></Form.Item>
          <Form.Item name="amount" label="Amount" rules={[{ required: true }]}><InputNumber min={0.01} max={payFor ? payable(payFor) - received(payFor) : undefined} precision={2} style={{ width: "100%" }} /></Form.Item>
          <Form.Item name="reference" label="Reference"><Input maxLength={128} /></Form.Item>
        </Form>
      </Modal>
      {failed.map((q) => (
        <Alert key={q.key} style={{ marginBottom: 12 }} type="error" showIcon message={`Saved order not accepted: ${q.label}`} description={q.error}
          action={<Button size="small" danger onClick={() => discardQueued(q.key)}>Discard</Button>} />
      ))}
    </>
  );
}

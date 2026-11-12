import { PrinterOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Button, Modal, Select, Skeleton, Typography } from "antd";
import { menuApi } from "../api";
import { getPaperWidth, printBill, setPaperWidth, type PaperWidth } from "../printing";

export function BillModal({ orderId, currency, onClose }: { orderId: number | null; currency: string; onClose: () => void }) {
  const bill = useQuery({ queryKey: ["bill", orderId], queryFn: () => menuApi.bill(orderId as number), enabled: orderId !== null });
  const b = bill.data;
  const [paper, setPaper] = useState<PaperWidth>(getPaperWidth());
  const m = (v: string) => `${currency} ${Number(v).toFixed(2)}`;
  return (
    <Modal open={orderId !== null} onCancel={onClose} title={b?.tax_invoice ? "Tax invoice" : "Bill"} width={420}
      footer={[<Select key="w" value={paper} style={{ width: 110 }} onChange={(v: PaperWidth) => { setPaper(v); setPaperWidth(v); }} options={[{ value: "80", label: "80 mm paper" }, { value: "58", label: "58 mm paper" }]} />, <Button key="p" icon={<PrinterOutlined />} disabled={!b} onClick={() => b && printBill(b, currency)}>Print</Button>, <Button key="c" type="primary" onClick={onClose}>Close</Button>]}>
      {!b ? <Skeleton active /> : (
        <div className="printable-bill">
          <Typography.Title level={4} style={{ margin: 0 }}>{b.restaurant}</Typography.Title>
          <div>{b.address}</div>
          {b.legal_gstin && <div>GSTIN: {b.legal_gstin}</div>}
          <div>Bill no: {b.order_number} · {new Date(b.date).toLocaleString()}</div>
          {b.place_of_supply && <div>Place of supply: {b.place_of_supply}</div>}
          <hr />
          {b.lines.map((l, i) => <div key={i} style={{ display: "flex", justifyContent: "space-between" }}><span>{l.name}{(l as { complimentary?: boolean }).complimentary ? " (complimentary)" : ""} × {l.quantity} @ {l.unit_price}</span><span>{m(l.amount)}</span></div>)}
          <hr />
          <div style={{ display: "flex", justifyContent: "space-between" }}><span>Subtotal</span><span>{m(b.subtotal)}</span></div>
          {b.gst.map((g) => (<div key={g.rate}>
            <div style={{ display: "flex", justifyContent: "space-between" }}><span>CGST {Number(g.rate) / 2}% on {m(g.taxable)}</span><span>{m(g.cgst)}</span></div>
            <div style={{ display: "flex", justifyContent: "space-between" }}><span>SGST {Number(g.rate) / 2}%</span><span>{m(g.sgst)}</span></div></div>))}
          {Number(b.discount) > 0 && <div style={{ display: "flex", justifyContent: "space-between" }}><span>Discount{b.discount_reason ? ` (${b.discount_reason})` : ""}</span><span>-{m(b.discount)}</span></div>}
          {Number(b.service_charge) > 0 && <div style={{ display: "flex", justifyContent: "space-between" }}><span>Service charge</span><span>{m(b.service_charge)}</span></div>}
          {Number(b.round_off) !== 0 && <div style={{ display: "flex", justifyContent: "space-between" }}><span>Round off</span><span>{m(b.round_off)}</span></div>}
          <div style={{ display: "flex", justifyContent: "space-between", fontWeight: 700 }}><span>Total</span><span>{m(b.total)}</span></div>
          {Number(b.tip) > 0 && <div style={{ display: "flex", justifyContent: "space-between" }}><span>Tip</span><span>{m(b.tip)}</span></div>}
          {Number(b.tip) > 0 && <div style={{ display: "flex", justifyContent: "space-between", fontWeight: 700 }}><span>Amount payable</span><span>{m(b.payable)}</span></div>}
          {b.payments.map((p, i) => <div key={i} style={{ display: "flex", justifyContent: "space-between" }}><span>Paid ({p.method})</span><span>{m(p.amount)}</span></div>)}
          {b.notice && <Typography.Paragraph type="secondary" style={{ marginTop: 8 }}>{b.notice}</Typography.Paragraph>}
        </div>
      )}
    </Modal>
  );
}

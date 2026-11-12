import qrcode from "qrcode-generator";
import type { Bill, OrderRow } from "./api";

export type PaperWidth = "58" | "80";
const KEY = "restoiq.paper";

export function getPaperWidth(): PaperWidth {
  return localStorage.getItem(KEY) === "58" ? "58" : "80";
}
export function setPaperWidth(w: PaperWidth) {
  localStorage.setItem(KEY, w);
}

const AUTO_KEY = "restoiq.autokot";
export const getAutoKot = () => localStorage.getItem(AUTO_KEY) === "1";
export const setAutoKot = (on: boolean) => localStorage.setItem(AUTO_KEY, on ? "1" : "0");

const esc = (v: unknown) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] as string));
const row = (l: string, r: string, bold = false) => `<div class="r${bold ? " b" : ""}"><span>${l}</span><span>${r}</span></div>`;

function printHtml(title: string, body: string) {
  const mm = getPaperWidth();
  const iframe = document.createElement("iframe");
  iframe.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0";
  document.body.appendChild(iframe);
  const doc = iframe.contentDocument!;
  doc.open();
  doc.write(`<!doctype html><html><head><title>${esc(title)}</title><style>
    @page { size: ${mm}mm auto; margin: 2mm; }
    body { width: ${Number(mm) - 6}mm; margin: 0; font: ${mm === "58" ? 11 : 12}px/1.35 "Courier New", monospace; color: #000; }
    .c { text-align: center } .b { font-weight: 700 } .big { font-size: 1.35em }
    .r { display: flex; justify-content: space-between; gap: 6px } .r span:first-child { flex: 1; word-break: break-word }
    .line { border-top: 1px dashed #000; margin: 4px 0 } .n { padding-left: 8px; font-style: italic }
  </style></head><body>${body}</body></html>`);
  doc.close();
  iframe.onload = () => undefined;
  setTimeout(() => {
    iframe.contentWindow!.focus();
    iframe.contentWindow!.print();
    setTimeout(() => iframe.remove(), 1500);
  }, 150);
}

export function printKot(order: OrderRow, kotNo: number, tableName: string | null, restaurant: string, duplicate = false) {
  const items = order.items.filter((i) => i.kot_no === kotNo && i.status === "active");
  const body = `
    <div class="c b">${esc(restaurant)}</div>
    <div class="c b big">KOT #${kotNo}</div>
    ${duplicate ? '<div class="c b">*** REPRINT / DUPLICATE ***</div>' : ""}
    <div class="line"></div>
    ${row("Order", esc(order.order_number))}
    ${row(order.order_type === "dine_in" ? "Table" : "Type", esc(order.order_type === "dine_in" ? tableName ?? "-" : order.order_type.toUpperCase()), true)}
    ${order.contact_name || order.contact_phone ? row("Customer", esc([order.contact_name, order.contact_phone].filter(Boolean).join(" "))) : ""}
    ${order.delivery_address ? `<div class="n">${esc(order.delivery_address)}</div>` : ""}
    ${row("Time", esc(new Date().toLocaleString("en-IN")))}
    <div class="line"></div>
    ${items.map((i) => `${row(esc(i.name), `x ${i.quantity}`, true)}${i.addons?.length ? `<div class="n">+ ${esc(i.addons.map((a) => a.name).join(", "))}</div>` : ""}${i.notes ? `<div class="n">${esc(i.notes)}</div>` : ""}`).join("")}
    <div class="line"></div>
    <div class="c">${items.reduce((s, i) => s + i.quantity, 0)} item(s)</div>`;
  printHtml(`KOT ${kotNo} ${order.order_number}`, body);
}

export function printKotCancel(order: OrderRow, item: OrderRow["items"][number], tableName: string | null, restaurant: string) {
  const body = `
    <div class="c b">${esc(restaurant)}</div>
    <div class="c b big">*** CANCELLED ***</div>
    <div class="line"></div>
    ${row("Order", esc(order.order_number))}
    ${row(order.order_type === "dine_in" ? "Table" : "Type", esc(order.order_type === "dine_in" ? tableName ?? "-" : order.order_type.toUpperCase()), true)}
    ${row("KOT", `#${item.kot_no}`)}
    ${row("Time", esc(new Date().toLocaleString("en-IN")))}
    <div class="line"></div>
    ${row(esc(item.name), `x ${item.quantity}`, true)}
    ${item.cancel_reason ? `<div class="n">${esc(item.cancel_reason)}</div>` : ""}
    <div class="line"></div>
    <div class="c b">Do NOT prepare this item</div>`;
  printHtml(`Cancelled ${item.name} ${order.order_number}`, body);
}

function upiQr(b: Bill): string {
  const paid = b.payments.reduce((a, p) => a + Number(p.amount), 0);
  const due = Number(b.payable) - paid;
  if (!b.upi_id || due <= 0) return "";
  const url = `upi://pay?pa=${encodeURIComponent(b.upi_id)}&pn=${encodeURIComponent(b.restaurant.slice(0, 40))}&am=${due.toFixed(2)}&cu=INR&tn=${encodeURIComponent("Bill " + b.order_number)}`;
  const qr = qrcode(0, "M");
  qr.addData(url);
  qr.make();
  return `<div class="c">Scan to pay by UPI</div><div class="c">${qr.createSvgTag({ cellSize: 3, margin: 2, scalable: false })}</div><div class="c">${esc(b.upi_id)} · ${due.toFixed(2)}</div>`;
}

export function printBill(b: Bill, currency: string) {
  const m = (v: string) => Number(v).toFixed(2);
  const body = `
    <div class="c b big">${esc(b.restaurant)}</div>
    ${b.address ? `<div class="c">${esc(b.address)}</div>` : ""}
    ${b.legal_gstin ? `<div class="c">GSTIN: ${esc(b.legal_gstin)}</div>` : ""}
    <div class="c b">${b.tax_invoice ? "TAX INVOICE" : "BILL"}</div>
    <div class="line"></div>
    ${row("Bill no", esc(b.order_number))}
    ${b.order_type !== "dine_in" ? row("Type", esc(b.order_type.toUpperCase())) : ""}
    ${b.contact_name || b.contact_phone ? row("Customer", esc([b.contact_name, b.contact_phone].filter(Boolean).join(" "))) : ""}
    ${b.delivery_address ? `<div class="n">${esc(b.delivery_address)}</div>` : ""}
    ${row("Date", esc(new Date(b.date).toLocaleString("en-IN")))}
    ${b.place_of_supply ? row("Place of supply", esc(b.place_of_supply)) : ""}
    <div class="line"></div>
    ${b.lines.map((l) => `<div>${esc(l.name)}${l.addons?.length ? ` + ${esc(l.addons.join(", "))}` : ""}</div>${row(`&nbsp;&nbsp;${l.quantity} x ${m(l.unit_price)}`, m(l.amount))}`).join("")}
    <div class="line"></div>
    ${row("Subtotal", m(b.subtotal))}
    ${Number(b.discount) > 0 ? row(`Discount${b.discount_reason ? ` (${esc(b.discount_reason)})` : ""}`, `-${m(b.discount)}`) : ""}
    ${Number(b.service_charge) > 0 ? row("Service charge", m(b.service_charge)) : ""}
    ${b.gst.map((g) => `${row(`CGST ${Number(g.rate) / 2}% on ${m(g.taxable)}`, m(g.cgst))}${row(`SGST ${Number(g.rate) / 2}%`, m(g.sgst))}`).join("")}
    ${Number(b.round_off) !== 0 ? row("Round off", m(b.round_off)) : ""}
    <div class="line"></div>
    ${row(`TOTAL (${esc(currency)})`, m(b.total), true)}
    ${Number(b.tip) > 0 ? row("Tip", m(b.tip)) + row("Amount payable", m(b.payable), true) : ""}
    ${b.payments.map((p) => row(`Paid (${esc(p.method)})`, m(p.amount))).join("")}
    <div class="line"></div>
    ${upiQr(b)}
    ${b.notice ? `<div class="c">${esc(b.notice)}</div>` : ""}
    <div class="c">Thank you! Visit again</div>`;
  printHtml(`Bill ${b.order_number}`, body);
}

/** KOT built from a locally saved order, so the kitchen slip prints without internet. */
export function printQueuedKot(q: import("../../shared/offlineQueue").QueuedOrder) {
  const lines = q.lines ?? [];
  const body = `
    <div class="c b">${esc(q.restaurant ?? "")}</div>
    <div class="c b big">KOT (OFFLINE)</div>
    <div class="line"></div>
    ${row(q.orderType && q.orderType !== "dine_in" ? "Type" : "Table", esc(q.orderType && q.orderType !== "dine_in" ? q.orderType.toUpperCase() : q.tableName ?? "-"), true)}
    ${q.contact ? row("Customer", esc(q.contact)) : ""}
    ${row("Time", esc(new Date(q.createdAt).toLocaleString("en-IN")))}
    <div class="line"></div>
    ${lines.map((l) => row(esc(l.name), `x ${l.qty}`, true)).join("")}
    <div class="line"></div>
    <div class="c">${lines.reduce((s, l) => s + l.qty, 0)} item(s)</div>`;
  printHtml("KOT offline", body);
}

export function printProvisional(q: import("../../shared/offlineQueue").QueuedOrder, currency: string) {
  const m = (paise: number) => (paise / 100).toFixed(2);
  const c = q.charges!;
  const paid = (q.payments ?? []).reduce((t, p) => t + Number(p.amount), 0);
  const body = `
    <div class="c b">${esc(q.restaurant ?? "")}</div>
    <div class="c b big">PROVISIONAL BILL</div>
    <div class="c">Not a tax invoice. A numbered GST bill is issued once online.</div>
    <div class="line"></div>
    ${row("Time", esc(new Date(q.createdAt).toLocaleString("en-IN")))}
    ${q.orderType && q.orderType !== "dine_in" ? row("Type", esc(q.orderType.toUpperCase())) : ""}
    ${q.contact ? row("Customer", esc(q.contact)) : ""}
    <div class="line"></div>
    ${(q.lines ?? []).map((l) => `<div>${esc(l.name)}</div>${row(`&nbsp;&nbsp;${l.qty} x ${m(l.unitPaise)}`, m(l.unitPaise * l.qty))}`).join("")}
    <div class="line"></div>
    ${row("Subtotal", m(c.subtotal))}
    ${c.serviceCharge ? row("Service charge", m(c.serviceCharge)) : ""}
    ${row("GST", m(c.tax))}
    ${c.roundOff ? row("Round off", m(c.roundOff)) : ""}
    ${row(`TOTAL (${esc(currency)})`, m(c.total), true)}
    ${paid ? row("Received", paid.toFixed(2)) : ""}`;
  printHtml("Provisional bill", body);
}

import type { TaxInvoice } from "./api";

const esc = (v: unknown) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] as string));
const money = (v: number) => `₹${v.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export function printTaxInvoice(i: TaxInvoice) {
  const taxRows = i.igst > 0
    ? `<tr><td>IGST</td><td>${money(i.igst)}</td></tr>`
    : `<tr><td>CGST</td><td>${money(i.cgst)}</td></tr><tr><td>SGST</td><td>${money(i.sgst)}</td></tr>`;
  const iframe = document.createElement("iframe");
  iframe.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0";
  document.body.appendChild(iframe);
  const doc = iframe.contentDocument!;
  doc.open();
  doc.write(`<!doctype html><html><head><title>${esc(i.number)}</title><style>
    @page { size: A4; margin: 15mm; }
    body { font: 13px/1.5 Arial, sans-serif; color: #111; }
    h1 { font-size: 20px; margin: 0 0 4px } .draft { color: #b45309; border: 1px solid #b45309; padding: 6px 10px; margin: 10px 0 }
    .cols { display: flex; gap: 30px; margin: 14px 0 } .cols > div { flex: 1 }
    table { width: 100%; border-collapse: collapse; margin-top: 10px } td, th { border: 1px solid #999; padding: 6px 8px; text-align: left }
    td + td, th + th { text-align: right } .tot td { font-weight: 700 } small { color: #555 }
  </style></head><body>
    <h1>TAX INVOICE</h1>
    <div>Invoice no: <b>${esc(i.number)}</b> &nbsp; Date: <b>${esc(i.date)}</b></div>
    ${i.draft ? `<div class="draft">DRAFT: seller GST details are not set up yet. This is a payment receipt, not a valid tax invoice.</div>` : ""}
    <div class="cols">
      <div><b>From</b><br>${esc(i.seller.name)}<br>${esc(i.seller.address)}<br>GSTIN: ${esc(i.seller.gstin)}</div>
      <div><b>Billed to</b><br>${esc(i.buyer.name)}<br>${esc(i.buyer.address)}<br>${i.buyer.gstin ? `GSTIN: ${esc(i.buyer.gstin)}` : "GSTIN: unregistered"}</div>
    </div>
    <table><tr><th>Description (SAC ${esc(i.sac)})</th><th>Amount</th></tr>
      <tr><td>${esc(i.description)}<br><small>Period ${esc(i.period_start)} to ${esc(i.period_end)}</small></td><td>${money(i.subtotal)}</td></tr>
      ${taxRows}<tr class="tot"><td>Total (paid via Razorpay)</td><td>${money(i.total)}</td></tr></table>
    <p><small>This is a computer-generated invoice.</small></p>
  </body></html>`);
  doc.close();
  setTimeout(() => { iframe.contentWindow!.focus(); iframe.contentWindow!.print(); setTimeout(() => iframe.remove(), 1500); }, 150);
}

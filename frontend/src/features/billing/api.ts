import { api } from "../../shared/api/client";

export interface BillingInvoice {
  id: number;
  number: string;
  plan_name: string;
  outlets: number;
  subtotal: number;
  gst: number;
  total: number;
  status: string;
  period_start: string;
  period_end: string;
  paid_at: string | null;
}

export interface BillingStatus {
  subscription: { status: string; trial_ends_at: string | null; days_left: number | null; locked: boolean };
  payments_enabled: boolean;
  price: { monthly: number; yearly: number; gst_percent: number };
  invoices: BillingInvoice[];
  autorenew: { status: string; billing_cycle: "monthly" | "yearly"; amount: number } | null;
}

export interface Checkout {
  key_id: string;
  razorpay_order_id: string;
  amount: number;
  currency: string;
  invoice_number: string;
  email: string | null;
  description: string;
}

export interface AutoRenewStart { key_id: string; subscription_id: string; email: string | null; description: string; amount: number; first_charge_at: number | null }
export interface AutoRenewResponse { razorpay_payment_id: string; razorpay_subscription_id: string; razorpay_signature: string }

export interface RazorpayResponse {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => { open: () => void; on: (event: string, handler: () => void) => void };
  }
}

let script: Promise<void> | null = null;
export function loadCheckout(): Promise<void> {
  if (window.Razorpay) return Promise.resolve();
  script ??= new Promise((resolve, reject) => {
    const tag = document.createElement("script");
    tag.src = "https://checkout.razorpay.com/v1/checkout.js";
    tag.onload = () => resolve();
    tag.onerror = () => { script = null; reject(new Error("Could not load the payment window. Check your internet connection.")); };
    document.body.appendChild(tag);
  });
  return script;
}

export interface TaxInvoice {
  number: string; date: string; draft: boolean; sac: string; description: string;
  period_start: string; period_end: string; subtotal: number; gst: number; total: number;
  cgst: number; sgst: number; igst: number;
  seller: { name: string; gstin: string; address: string };
  buyer: { name: string; gstin: string | null; address: string; state_code: string };
}

export const billingApi = {
  taxInvoice: (id: number) => api<TaxInvoice>(`/billing/invoices/${id}/tax-invoice`),
  status: () => api<BillingStatus>("/billing/status"),
  checkout: (billing_cycle: "monthly" | "yearly") =>
    api<Checkout>("/billing/checkout", { method: "POST", body: JSON.stringify({ billing_cycle }) }),
  startAutoRenew: (billing_cycle: "monthly" | "yearly") => api<AutoRenewStart>("/billing/autorenew", { method: "POST", body: JSON.stringify({ billing_cycle }) }),
  verifyAutoRenew: (body: AutoRenewResponse) => api<unknown>("/billing/autorenew/verify", { method: "POST", body: JSON.stringify(body) }),
  cancelAutoRenew: () => api<unknown>("/billing/autorenew/cancel", { method: "POST" }),
  verify: (body: RazorpayResponse) => api<unknown>("/billing/verify", { method: "POST", body: JSON.stringify(body) }),
};

import { api } from "../../shared/api/client";

export interface PlatformRestaurant {
  id: number; name: string; created_at: string; owner_email: string | null; owner_name: string | null;
  mobile: string | null; city: string | null; plan_name: string; subscription_status: string;
  trial_ends_at: string | null; outlets: number; users: number; amount_due: number;
  paid_total: number; last_paid_at: string | null; days_left: number | null; plan_ends_at: string | null;
  reminders_sent: number; last_reminder_at: string | null; billing_cycle: string | null;
}
export interface ReminderEntry {
  id: number; tenant_id: number; restaurant: string | null; kind: string; days_left: number | null;
  to_email: string; status: string; created_at: string;
}
export interface PlanPrice { plan_name: string; price_inr: number; yearly_price_inr: number; gst_percent: number; description: string }
export interface PlatformInvoice {
  id: number; number: string; tenant_id: number; tenant_name: string | null; plan_name: string; outlets: number;
  subtotal: number; gst: number; total: number; status: string; period_start: string; period_end: string;
  created_at: string; paid_at: string | null;
}

export const platformApi = {
  restaurants: () => api<{ restaurants: PlatformRestaurant[] }>("/platform/restaurants"),
  changeSubscription: (tenantId: number, action: "extend_trial" | "activate", days = 7) =>
    api<{ status: string }>(`/platform/restaurants/${tenantId}/subscription`, { method: "POST", body: JSON.stringify({ action, days }) }),
  remind: (tenantId: number) => api<{ sent_to: string }>(`/platform/restaurants/${tenantId}/remind`, { method: "POST" }),
  reminders: () => api<{ reminders: ReminderEntry[] }>("/platform/reminders"),
  plans: () => api<{ plans: PlanPrice[] }>("/platform/plans"),
  updatePlan: (name: string, body: { price_inr: number; yearly_price_inr: number; gst_percent: number }) =>
    api<PlanPrice>(`/platform/plans/${name}`, { method: "PUT", body: JSON.stringify(body) }),
  invoices: () => api<{ invoices: PlatformInvoice[]; totals: { pending: number; paid: number } }>("/platform/invoices"),
  createInvoice: (tenant_id: number) =>
    api<PlatformInvoice>("/platform/invoices", { method: "POST", body: JSON.stringify({ tenant_id }) }),
  setInvoiceStatus: (inv: PlatformInvoice, status: string) =>
    api<PlatformInvoice>(`/platform/invoices/${inv.id}?tenant_id=${inv.tenant_id}`, { method: "PATCH", body: JSON.stringify({ status }) }),
};

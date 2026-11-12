import { api } from "../../shared/api/client";

export interface SubscriptionPlan {
  name: string;
  default: boolean;
  entitlements: { description: string };
}

export const adminApi = {
  subscriptionPlans: () => api<{ plans: SubscriptionPlan[]; current_plan: string }>("/subscription/plans"),
};

export interface StaffMember { id: number; email: string; full_name: string | null; role: string; is_active: boolean; outlet_ids: number[] }

export const staffApi = {
  list: () => api<{ staff: StaffMember[]; assignable_roles: string[] }>("/staff"),
  create: (body: { email: string; full_name?: string; role: string; password: string; outlet_ids: number[] }) =>
    api<StaffMember>("/staff", { method: "POST", body: JSON.stringify(body) }),
  update: (id: number, body: Partial<{ full_name: string; role: string; is_active: boolean; outlet_ids: number[]; password: string }>) =>
    api<StaffMember>(`/staff/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
};

export interface AdminTable { id: number; name: string; seats: number; status: string; floor_name: string | null }

export const tablesApi = {
  list: (outletId: number) => api<{ tables: AdminTable[] }>(`/outlets/${outletId}/tables-admin`),
  create: (outletId: number, body: { name: string; seats: number; floor_name?: string }) =>
    api<AdminTable>(`/outlets/${outletId}/tables`, { method: "POST", body: JSON.stringify(body) }),
  bulk: (outletId: number, body: { prefix: string; count: number; seats: number; floor_name?: string }) =>
    api<{ created: AdminTable[] }>(`/outlets/${outletId}/tables/bulk`, { method: "POST", body: JSON.stringify(body) }),
  update: (outletId: number, id: number, body: { name?: string; seats?: number }) =>
    api<AdminTable>(`/outlets/${outletId}/tables/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  remove: (outletId: number, id: number) => api<void>(`/outlets/${outletId}/tables/${id}`, { method: "DELETE" }),
};

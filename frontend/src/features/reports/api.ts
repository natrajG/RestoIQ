import { api } from "../../shared/api/client";

export interface Report {
  period: "weekly" | "monthly"; days: number; outlet: string; currency: string; from: string; to: string;
  sales: {
    orders: number; revenue: string; average_bill: string | null;
    by_weekday: { weekday: string; revenue: string; orders: number }[];
    by_hour: { hour: number; revenue: string; orders: number }[];
    top_items: { item: string; quantity: number; revenue: string }[];
    top_items_by_weekday: { weekday: string; items: { item: string; quantity: number }[] }[];
  };
  previous_sales: { revenue: string; orders: number; average_bill: string | null };
  change: { revenue_pct: number | null; orders_pct: number | null };
  occupancy: { available: boolean; sessions: number; avg_dwell_minutes: number | null; busiest_tables: { table: string; sessions: number; occupied_hours: number; avg_minutes: number }[]; note: string };
  tasks: { created: number; completed: number; overdue: number; avg_completion_minutes: number | null; by_type: Record<string, { created: number; completed: number }> };
  highlights: string[];
}
export interface SavedReport { id: number; period: "weekly" | "monthly"; period_end: string; payload: Report }

export const reportsApi = {
  live: (outletId: number, period: "weekly" | "monthly") => api<Report>(`/outlets/${outletId}/reports/${period}`),
  saved: (outletId: number) => api<{ reports: SavedReport[] }>(`/outlets/${outletId}/reports`),
};

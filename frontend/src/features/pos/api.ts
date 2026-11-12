import { api } from "../../shared/api/client";

export interface Outlet {
  id: number;
  name: string;
  timezone: string;
  currency: string;
  subscription_plan?: string;
}

export interface DiningTable {
  id: number;
  name: string;
  seats: number;
  status: string;
}

export interface MenuItem {
  id: number;
  category_id: number | null;
  cost_price: string | null;
  name: string;
  sku: string;
  price: string;
  tax_rate: string;
  active: boolean;
  variants: MenuOption[];
  addons: MenuOption[];
}

export interface MenuOption { id: number; name: string; price: string }

export function lineUnitPrice(item: MenuItem, variantId?: number, addonIds: number[] = []): number {
  const variant = item.variants.find((v) => v.id === variantId);
  return (variant ? Number(variant.price) : Number(item.price)) + item.addons.filter((a) => addonIds.includes(a.id)).reduce((t, a) => t + Number(a.price), 0);
}

export function lineLabel(item: MenuItem, variantId?: number, addonIds: number[] = []): string {
  const variant = item.variants.find((v) => v.id === variantId);
  const extras = item.addons.filter((a) => addonIds.includes(a.id)).map((a) => a.name);
  return `${item.name}${variant ? ` (${variant.name})` : ""}${extras.length ? ` + ${extras.join(", ")}` : ""}`;
}

export interface MenuCategory { id: number; name: string; sort_order: number }
export interface Bill {
  restaurant: string; legal_gstin: string | null; address: string | null; order_number: string; date: string; order_type: string; contact_name: string | null; contact_phone: string | null; delivery_address: string | null; place_of_supply: string | null;
  lines: { name: string; addons: string[]; quantity: number; unit_price: string; amount: string; gst_rate: string }[];
  subtotal: string; gst: { rate: string; taxable: string; cgst: string; sgst: string; total_tax: string }[];
  tax_total: string; discount: string; discount_reason: string | null; service_charge: string; round_off: string; tip: string; payable: string; total: string; payments: { method: string; amount: string }[]; tax_invoice: boolean; notice: string | null; upi_id: string | null;
}

export interface GstReport {
  lines: { date: string; gst_rate: string; taxable: string; cgst: string; sgst: string; tax: string }[];
  daily: { date: string; bills: number; first_bill: string; last_bill: string; discount: string; total: string }[];
  totals: { taxable: string; cgst: string; sgst: string; bills: number; total: string }; composition: boolean; note: string;
}

export interface MenuImportReport {
  created: number; updated: number; errors: number; saved?: boolean;
  rows: { row: number; name: string; category: string; code: string; price: string; gst: string; status: "new" | "update" | "error"; message: string | null }[];
}

export const menuApi = {
  gstReport: (o: number, from: string, to: string) => api<GstReport>(`/outlets/${o}/reports/gst?from=${from}&to=${to}`),
  categories: (o: number) => api<MenuCategory[]>(`/outlets/${o}/menu/categories`),
  addCategory: (o: number, name: string) => api<MenuCategory>(`/outlets/${o}/menu/categories`, { method: "POST", body: JSON.stringify({ name }) }),
  deleteCategory: (o: number, id: number) => api<void>(`/outlets/${o}/menu/categories/${id}`, { method: "DELETE" }),
  addOption: (o: number, itemId: number, body: { kind: "variant" | "addon"; name: string; price: string }) =>
    api<MenuOption>(`/outlets/${o}/menu/items/${itemId}/options`, { method: "POST", body: JSON.stringify(body) }),
  removeOption: (o: number, itemId: number, optionId: number) =>
    api<void>(`/outlets/${o}/menu/items/${itemId}/options/${optionId}`, { method: "DELETE" }),
  addItem: (o: number, body: { category_id: number | null; name: string; sku: string; price: string; tax_rate: string }) =>
    api<{ id: number }>(`/outlets/${o}/menu/items`, { method: "POST", body: JSON.stringify({ ...body, restaurant_id: o }) }),
  deleteItem: (o: number, id: number) => api<void>(`/outlets/${o}/menu/items/${id}`, { method: "DELETE" }),
  importMenu: async (o: number, file: File, commit: boolean): Promise<MenuImportReport> => {
    const form = new FormData();
    form.append("file", file);
    const response = await fetch(`/api/v1/outlets/${o}/menu/import?commit=${commit}`, { method: "POST", body: form, credentials: "include" });
    const body = await response.json().catch(() => ({})) as MenuImportReport & { detail?: string };
    if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Import failed");
    return body;
  },
  updateItem: (o: number, id: number, body: Partial<{ name: string; category_id: number | null; price: string; tax_rate: string; active: boolean }>) =>
    api<unknown>(`/outlets/${o}/menu/items/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  gst: (o: number) => api<{ gst_scheme: "regular" | "composition" }>(`/outlets/${o}/gst-settings`),
  setGst: (o: number, gst_scheme: "regular" | "composition") => api<unknown>(`/outlets/${o}/gst-settings`, { method: "PUT", body: JSON.stringify({ gst_scheme }) }),
  billing: (o: number) => api<{ service_charge_pct: string; round_off: boolean; upi_id: string }>(`/outlets/${o}/billing-settings`),
  setBilling: (o: number, body: { service_charge_pct: number; round_off: boolean; upi_id?: string }) => api<unknown>(`/outlets/${o}/billing-settings`, { method: "PUT", body: JSON.stringify(body) }),
  bill: (orderId: number) => api<Bill>(`/orders/${orderId}/bill`),
};

export interface OrderRow { id: number; order_number: string; order_type: string; contact_name: string | null; contact_phone: string | null; delivery_address: string | null; status: string; table_id: number | null; total: string; payable: string; tip: string; service_charge: string; round_off: string; discount_total: string; discount_type: "percent" | "fixed" | null; discount_value: string; discount_reason: string | null; service_charge_waived: boolean; customer_id: number | null; covers: number | null; remark: string | null; staff_name: string | null; scheduled_for: string | null; complimentary_reason: string | null; complimentary_total: string; created_at: string; items: OrderItemRow[] }
export interface OrderItemRow { id: number; menu_item_id: number; name: string; quantity: number; notes: string | null; kot_no: number; status: "active" | "cancelled"; complimentary: boolean; cancel_reason: string | null; addons: { name: string; price: string }[] }
export type OrderEvent = "KOT_ACCEPTED" | "PREPARATION_STARTED" | "FOOD_READY" | "FOOD_PICKED_UP" | "FOOD_DELIVERED" | "BILL_REQUESTED" | "ORDER_COMPLETED" | "CUSTOMER_DEPARTED";

export interface OrderLineBody { menu_item_id: number; quantity: number; notes?: string; variant_id?: number; addon_ids?: number[] }

export const orderApi = {
  list: (o: number) => api<OrderRow[]>(`/outlets/${o}/orders?limit=100`),
  event: (orderId: number, event_type: OrderEvent) => api<OrderRow>(`/orders/${orderId}/events`, { method: "POST", body: JSON.stringify({ event_type }) }),
  addItems: (orderId: number, items: OrderLineBody[], key: string = crypto.randomUUID()) =>
    api<OrderRow>(`/orders/${orderId}/items`, { method: "POST", headers: { "Idempotency-Key": key }, body: JSON.stringify({ items }) }),
  setCharges: (orderId: number, body: { discount_type: "percent" | "fixed" | null; discount_value: number; discount_reason?: string; waive_service_charge: boolean; tip: number }) =>
    api<OrderRow>(`/orders/${orderId}/charges`, { method: "PUT", body: JSON.stringify(body) }),
  cancelItem: (orderId: number, itemId: number, reason: string) =>
    api<OrderRow>(`/orders/${orderId}/items/${itemId}/cancel`, { method: "POST", body: JSON.stringify({ reason }) }),
  get: (orderId: number) => api<OrderRow>(`/orders/${orderId}`),
  shift: (orderId: number, table_id: number) => api<OrderRow>(`/orders/${orderId}/shift`, { method: "POST", body: JSON.stringify({ table_id }) }),
  split: (orderId: number, lines: { item_id: number; quantity: number }[]) =>
    api<{ original: OrderRow; new: OrderRow }>(`/orders/${orderId}/split`, { method: "POST", body: JSON.stringify({ lines }) }),
  merge: (orderId: number, into_order_id: number) => api<OrderRow>(`/orders/${orderId}/merge`, { method: "POST", body: JSON.stringify({ into_order_id }) }),
  complimentary: (orderId: number, item_ids: number[], reason?: string) => api<OrderRow>(`/orders/${orderId}/complimentary`, { method: "PUT", body: JSON.stringify({ item_ids, reason }) }),
  void: (orderId: number, reason: string) => api<OrderRow>(`/orders/${orderId}/void`, { method: "POST", body: JSON.stringify({ reason }) }),
  pay: (orderId: number, body: { method: string; amount: string; reference?: string }, key: string) =>
    api<{ order_paid: boolean }>(`/orders/${orderId}/payments`, { method: "POST", headers: { "Idempotency-Key": key }, body: JSON.stringify(body) }),
};

export const posApi = {
  outlets: () => api<Outlet[]>("/outlets"),
  tables: (outletId: number) => api<DiningTable[]>(`/outlets/${outletId}/tables`),
  menu: (outletId: number) => api<MenuItem[]>(`/outlets/${outletId}/menu`),
  kitchen: (outletId: number) => api<OrderRow[]>(`/outlets/${outletId}/kitchen`),
  orders: (outletId: number) => api<unknown[]>(`/outlets/${outletId}/orders`),
  summary: (outletId: number) => api<Record<string, string | number>>(`/outlets/${outletId}/analytics/summary`),
  createOrder: (outletId: number, body: {
    restaurant_id: number;
    table_id?: number;
    order_type: "dine_in" | "takeaway" | "delivery";
    contact_name?: string; contact_phone?: string; delivery_address?: string; covers?: number; remark?: string; scheduled_for?: string; advance_amount?: number; advance_method?: string;
    items: OrderLineBody[];
  }, idempotencyKey: string) =>
    api<{ id: number; order_number: string }>(`/outlets/${outletId}/orders`, {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ ...body, discount_amount: "0" }),
    }),
};

export interface CashEntry { id: number; kind: "in" | "out"; amount: string; reason: string; category: string | null; pay_method: string; created_by: string | null; created_at: string }
export interface Cashbook {
  date: string; opening_cash: string; opening_known: boolean; cash_sales: string; petty_in: string; petty_out: string; expected_cash: string;
  unpaid_orders: number; account_cash: string; categories: string[]; entries: CashEntry[];
  unsettled: { id: number; order_number: string; order_type: string; total: string; status: string; scheduled_for: string | null }[];
  closed: null | { counted_cash: string; difference: string; note: string | null; closed_by: string | null };
}
export interface DayCloseRow { date: string; opening_cash: string; cash_sales: string; petty_in: string; petty_out: string; expected_cash: string; counted_cash: string; difference: string; note: string | null; closed_by: string | null }

export const cashApi = {
  book: (o: number) => api<Cashbook>(`/outlets/${o}/cashbook`),
  addPetty: (o: number, body: { kind: "in" | "out"; amount: number; reason: string; category?: string; pay_method?: string }) => api<Cashbook>(`/outlets/${o}/petty-cash`, { method: "POST", body: JSON.stringify(body) }),
  removePetty: (o: number, id: number) => api<Cashbook>(`/outlets/${o}/petty-cash/${id}`, { method: "DELETE" }),
  close: (o: number, body: { opening_cash?: number; counted_cash: number; note?: string }) => api<Cashbook>(`/outlets/${o}/day-close`, { method: "POST", body: JSON.stringify(body) }),
  history: (o: number) => api<DayCloseRow[]>(`/outlets/${o}/day-closes`),
};

export interface Customer {
  id: number; balance_due: string; name: string; phone: string | null; email: string | null; loyalty_points: number; birthday: string | null; anniversary: string | null;
  gstin: string | null; address: string | null; orders?: number; spent?: string; last_visit?: string | null;
}
export interface CustomerOrder { id: number; order_number: string; order_type: string; status: string; total: string; created_at: string; items: string[] }

export const customerApi = {
  list: (o: number, q: string) => api<Customer[]>(`/outlets/${o}/customer-book?q=${encodeURIComponent(q)}`),
  detail: (id: number) => api<Omit<Customer, "orders"> & { orders: CustomerOrder[] }>(`/customers/${id}`),
  update: (id: number, body: Partial<Customer> & { name: string }) => api<Customer>(`/customers/${id}`, { method: "PUT", body: JSON.stringify(body) }),
};

export interface TableLive { order_id: number; order_number: string; amount: string; waiter: string | null; covers: number | null; minutes: number; status: string }
export const tableLiveApi = { get: (o: number) => api<Record<string, TableLive>>(`/outlets/${o}/table-live`) };

export interface LedgerEntry { id: number; kind: "debit" | "credit"; amount: string; method: string | null; remark: string | null; created_by: string | null; created_at: string }
export const ledgerApi = {
  get: (id: number) => api<{ balance_due: string; entries: LedgerEntry[] }>(`/customers/${id}/ledger`),
  add: (id: number, body: { kind: "credit" | "debit"; amount: number; method?: string; remark?: string }) => api<{ balance_due: string; entries: LedgerEntry[] }>(`/customers/${id}/ledger`, { method: "POST", body: JSON.stringify(body) }),
};

export interface SalesSummary {
  from: string; to: string; bills: number; subtotal: string; complimentary: string; discount: string; tax: string; service_charge: string; round_off: string;
  total_sale: string; pending_collection: string; refunds: string;
  by_method: { method: string; count: number; amount: string }[]; by_type: { type: string; count: number; amount: string }[]; by_group: { group: string; quantity: number; amount: string }[]; by_item: { item: string; quantity: number; amount: string }[];
  reconciliation: { billed: string; collected: string; refunds: string; net_collected: string; on_customer_account: string; advance_on_open_bills: string; pending_collection: string; difference: string; note: string };
}
export const salesApi = { summary: (o: number, from: string, to: string) => api<SalesSummary>(`/outlets/${o}/reports/sales-summary?date_from=${from}&date_to=${to}`) };

export type ExceptionRow = { time: string; staff: string; type: string; label: string; bill: string; bill_status: string; amount: string | null; reason: string | null };
export type ExceptionsReport = { from: string; to: string; rows: ExceptionRow[]; labels: Record<string, string>;
  by_staff: { staff: string; actions: Record<string, { count: number; amount: string }> }[] };
export const exceptionsApi = { get: (o: number, from: string, to: string) => api<ExceptionsReport>(`/outlets/${o}/reports/exceptions?date_from=${from}&date_to=${to}`) };

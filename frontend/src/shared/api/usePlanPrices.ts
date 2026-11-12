import { useQuery } from "@tanstack/react-query";
import { api } from "./client";

export interface PublicPrices { monthly: number; yearly: number; gst: number }

// The only source of subscription prices: whatever the platform admin has set.
export function usePlanPrices() {
  const q = useQuery({
    queryKey: ["public-plan-prices"],
    staleTime: 60_000,
    queryFn: async (): Promise<PublicPrices> => {
      const r = await api<{ plans: Record<string, { price_inr: number; yearly_price_inr: number; gst_percent: number }> }>("/public/plans");
      const p = r.plans.RESTOIQ_POS;
      if (!p) throw new Error("Pricing unavailable");
      return { monthly: p.price_inr, yearly: p.yearly_price_inr, gst: p.gst_percent };
    },
  });
  return { prices: q.data, isLoading: q.isLoading };
}

export const formatInr = (n: number) => `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

// Same maths as the server's compute_charges (no discount), in whole paise to avoid float drift.
export interface OfflineLine { name: string; qty: number; unitPaise: number; rate: number }
export interface OfflineCharges { subtotal: number; serviceCharge: number; tax: number; roundOff: number; total: number }

const half = (x: number) => Math.round(x + 1e-9);

function allocate(amount: number, weights: number[]): number[] {
  const total = weights.reduce((a, b) => a + b, 0);
  if (total <= 0) return weights.map(() => 0);
  const shares: number[] = [];
  let used = 0;
  for (const w of weights.slice(0, -1)) { const s = half((amount * w) / total); shares.push(s); used += s; }
  return [...shares, amount - used];
}

export function computeOffline(lines: OfflineLine[], servicePct: number, composition: boolean, roundOn: boolean): OfflineCharges {
  const byRate = new Map<number, number>();
  for (const l of lines) {
    const rate = composition ? 0 : l.rate;
    byRate.set(rate, (byRate.get(rate) ?? 0) + l.unitPaise * l.qty);
  }
  const rates = [...byRate.keys()].sort((a, b) => a - b);
  const bases = rates.map((r) => byRate.get(r)!);
  const subtotal = bases.reduce((a, b) => a + b, 0);
  const service = half((subtotal * servicePct) / 100);
  const taxable = bases.map((b, i) => b + allocate(service, bases)[i]);
  const tax = taxable.reduce((s, t, i) => s + half((t * rates[i]) / 100), 0);
  const before = subtotal + service + tax;
  const total = roundOn ? half(before / 100) * 100 : before;
  return { subtotal, serviceCharge: service, tax, roundOff: total - before, total };
}

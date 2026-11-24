import type { BillingPeriod, FreeTrial } from "@/features/billing/model/purchases";

/** `date` moved on by whole months, kept to the month's last day: Jan 31 + 1 month is Feb 28. */
function addMonths(date: Date, months: number): Date {
  const target = new Date(date.getFullYear(), date.getMonth() + months, 1, date.getHours(), date.getMinutes());
  const lastDay = new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate();
  target.setDate(Math.min(date.getDate(), lastDay));
  return target;
}

/**
 * The next payment after today: when a free trial ends, or one period on. The store charges
 * on that day; the page only says so.
 */
export function nextChargeDate(trial: FreeTrial | undefined, period: BillingPeriod, now: Date): Date {
  if (!trial) return addMonths(now, period === "yearly" ? 12 : 1);
  switch (trial.unit) {
    case "day":
      return new Date(now.getFullYear(), now.getMonth(), now.getDate() + trial.count, now.getHours(), now.getMinutes());
    case "week":
      return new Date(now.getFullYear(), now.getMonth(), now.getDate() + 7 * trial.count, now.getHours(), now.getMinutes());
    case "month":
      return addMonths(now, trial.count);
    case "year":
      return addMonths(now, 12 * trial.count);
  }
}

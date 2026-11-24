/**
 * What the plans page says about the plan: what it gives, and what is paid today and next
 * (the store owns the prices). Nothing here invents a number.
 */
import type { TimelineRow } from "@/features/billing/components/PlanPicker";
import { nextChargeDate } from "@/features/billing/model/planDates";
import type { BillingPeriod, FreeTrial } from "@/features/billing/model/purchases";
import { formatDate } from "@/lib/datetime/format";
import type { Translate } from "@/lib/i18n/translate";

/** What the plan gives, in the owner's words (2026-11-24): what it helps with, never a count
 * or which model answers. */
const BENEFITS = [
  "upgrade.benefit_chat",
  "upgrade.benefit_maths",
  "upgrade.benefit_physics",
  "upgrade.benefit_chemistry",
  "upgrade.benefit_calculator",
  "upgrade.benefit_images",
  "settings.web_search",
  "upgrade.benefit_transcription",
  "upgrade.benefit_pdf",
  "upgrade.benefit_scanner",
] as const;

export function planBenefits(t: Translate): string[] {
  return BENEFITS.map((key) => t(key));
}

/** " / month" or " / year", after a price. */
export function perPeriodKey(period: BillingPeriod): string {
  return period === "yearly" ? "upgrade.per_year_suffix" : "upgrade.per_month_suffix";
}

/** How much less a year costs than twelve months, in whole percent (rounded down, so the
 * page never claims more than the store's prices give); none when it is not less. */
export function yearlySaving(packages: Partial<Record<BillingPeriod, { price: number }>>): number | null {
  const monthly = packages.monthly?.price;
  const yearly = packages.yearly?.price;
  if (!monthly || !yearly || !(monthly > 0)) return null;
  const percent = Math.floor((1 - yearly / (12 * monthly)) * 100);
  return percent >= 1 ? percent : null;
}

/** "Start 3-day free trial": the button names the trial's length. */
export function startTrialText(trial: FreeTrial, t: Translate): string {
  return t(`upgrade.start_trial_${trial.unit}`, { count: trial.count });
}

/** "$5.00 / month, billed yearly", from the store's own per-month figure for the year. */
export function perMonthLine(pkg: { period: BillingPeriod; pricePerMonth?: string | null } | undefined, t: Translate): string | null {
  if (!pkg || pkg.period !== "yearly" || !pkg.pricePerMonth) return null;
  return t("upgrade.per_month_billed_yearly", { price: pkg.pricePerMonth });
}

/** "7 days free", "1 month free". */
function trialText(trial: FreeTrial, t: Translate): string {
  return t(`upgrade.trial_${trial.unit}`, { count: trial.count });
}

/** What is paid today and on the next payment's day; none until the store says a price. */
export function timelineRows(
  price: string | undefined,
  period: BillingPeriod,
  trial: FreeTrial | undefined,
  now: Date,
  t: Translate,
): [TimelineRow, TimelineRow] | null {
  if (!price) return null;
  const date = formatDate(nextChargeDate(trial, period, now), "monthDayYear");
  if (trial) {
    return [
      { label: t("upgrade.due_today"), amount: trial.priceString, chip: trialText(trial, t) },
      { label: t("upgrade.due_on", { date }), amount: price },
    ];
  }
  return [
    { label: t("upgrade.due_today"), amount: price },
    { label: t("upgrade.renews_on", { date }), amount: price },
  ];
}

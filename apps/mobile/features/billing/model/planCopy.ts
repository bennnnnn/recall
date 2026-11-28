/**
 * What the plans page says about the plan: what it gives, and what is paid today and next
 * (the store owns the prices). Nothing here invents a number.
 */
import { nextChargeDate } from "@/features/billing/model/planDates";
import type { BillingPeriod, FreeTrial } from "@/features/billing/model/purchases";
import { formatDate } from "@/lib/datetime/format";
import type { Translate } from "@/lib/i18n/translate";

/**
 * What Pro adds to Free, never a count or which model answers (owner, 2026-11-24). The
 * page listed maths, physics, chemistry, the calculator, web search, PDFs and the scanner,
 * which Free has too, and "Unlimited chat" without the daily guard behind it. Each line
 * here is one of Pro's allowances in apps/api/app/core/settings/plans.py, larger than
 * Free's or Free's 0 (`PRO_ADDS`, which planCopy.test.ts holds to that file).
 */
export const PRO_ADDS = {
  // Unlimited messages; a daily token budget guards against a runaway account.
  "upgrade.benefit_chat": ["daily_message_limit", "daily_token_limit"],
  "upgrade.benefit_searches": ["daily_tavily_searches"],
  "upgrade.benefit_more_images": ["daily_image_generations"],
  "upgrade.benefit_lookups": ["daily_image_searches"],
  "upgrade.benefit_documents": ["daily_document_limit"],
  "upgrade.benefit_transcription": ["daily_speech_transcriptions"],
  // The feature's own name, one key in every language.
  "chat.live_talk_a11y": ["monthly_live_talk_minutes"],
  "upgrade.benefit_read_aloud": ["daily_speech_tts"],
  "upgrade.benefit_storage": ["library_storage_bytes"],
} as const;

const BENEFITS = Object.keys(PRO_ADDS) as (keyof typeof PRO_ADDS)[];

export function planBenefits(t: Translate): string[] {
  return BENEFITS.map((key) => t(key));
}

/** " / month" or " / year", after a price. */
function perPeriodKey(period: BillingPeriod): string {
  return period === "yearly" ? "upgrade.per_year_suffix" : "upgrade.per_month_suffix";
}

/** "$7.99 / month": a package's price with its period, as the button and the reminder say it. */
export function priceWithPeriod(pkg: { priceString: string; period: BillingPeriod }, t: Translate): string {
  return `${pkg.priceString}${t(perPeriodKey(pkg.period))}`;
}

/** How much less a year costs than twelve months, in whole percent (rounded down, so the
 * page never claims more than the store's prices give); none when it is not less. */
export function yearlySaving(packages: Partial<Record<BillingPeriod, { price: number }>>): number | null {
  const monthly = packages.monthly?.price;
  const yearly = packages.yearly?.price;
  if (!monthly || !yearly || !(monthly > 0)) return null;
  // Rounded to a ten-thousandth first: 1 − 0.8 is 0.19999… in floating point, and a floor
  // alone would call an exact 20% "19%".
  const percent = Math.floor(Math.round((1 - yearly / (12 * monthly)) * 1e6) / 1e4);
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

/** One row of the page's dates: what is paid, and when ("Due today", "$0.00", "3 days free"). */
export type TimelineRow = { label: string; amount: string; chip?: string };

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

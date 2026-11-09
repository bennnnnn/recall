import type { Usage } from "@/lib/api";

/** The day's count as GET /usage/today gives it, or a turn's `done` (which has no `remaining`). */
type DayCount = Pick<Usage, "daily_limit" | "used_tokens" | "messages_used" | "daily_messages"> &
  Partial<Pick<Usage, "remaining">>;

export function usageUsedTokens(usage: DayCount): number {
  if (usage.used_tokens != null) return usage.used_tokens;
  return Math.max(0, usage.daily_limit - (usage.remaining ?? usage.daily_limit));
}

export function usageUsedPercent(usage: DayCount): number {
  if (usage.daily_limit <= 0) return 0;
  return Math.min(100, (usageUsedTokens(usage) / usage.daily_limit) * 100);
}

export function usageRemainingPercent(usage: Usage): number {
  if (usage.daily_limit <= 0) return 0;
  return Math.max(0, Math.min(100, (usage.remaining / usage.daily_limit) * 100));
}

/** The day's messages as used and offered, or null from a server that counts only tokens. */
export function usageMessages(usage: DayCount): { used: number; total: number } | null {
  const total = usage.daily_messages ?? 0;
  return total > 0 ? { used: Math.min(total, usage.messages_used ?? 0), total } : null;
}

/** The share of the day used, a whole 0 to 100: by messages when the server counts them. */
export function dayUsedPercent(usage: DayCount): number {
  const messages = usageMessages(usage);
  if (messages) return Math.round(Math.min(100, (messages.used / messages.total) * 100));
  return Math.round(usageUsedPercent(usage));
}

export function formatUsageSummary(
  usage: Usage,
  isPaid: boolean,
  t: (key: string, opts?: Record<string, unknown>) => string,
): string {
  const messages = usageMessages(usage);
  if (messages) {
    const left = messages.total - messages.used;
    if (left <= 0) return isPaid ? t("settings.usage_exhausted_paid") : t("settings.usage_exhausted");
    return t("settings.usage_messages_left", { left, total: messages.total });
  }
  if (usage.remaining <= 0) {
    return isPaid ? t("settings.usage_exhausted_paid") : t("settings.usage_exhausted");
  }
  const pct = Math.round(usageRemainingPercent(usage));
  return isPaid ? t("settings.usage_left_paid", { pct }) : t("settings.usage_left", { pct });
}

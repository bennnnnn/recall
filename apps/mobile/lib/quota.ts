import type { Usage } from "@/lib/api";

export function usageUsedTokens(usage: Usage): number {
  if (usage.used_tokens != null) return usage.used_tokens;
  return Math.max(0, usage.daily_limit - usage.remaining);
}

export function usageUsedPercent(usage: Usage): number {
  if (usage.daily_limit <= 0) return 0;
  return Math.min(100, (usageUsedTokens(usage) / usage.daily_limit) * 100);
}

export function usageRemainingPercent(usage: Usage): number {
  if (usage.daily_limit <= 0) return 0;
  return Math.max(0, Math.min(100, (usage.remaining / usage.daily_limit) * 100));
}

export function isQuotaErrorPayload(payload: {
  type?: string;
  code?: string;
  message?: string;
}): boolean {
  if (payload.code === "quota_exceeded") return true;
  return /free limit|daily limit|today'?s limit/i.test(payload.message ?? "");
}

export function isQuotaErrorMessage(message: string): boolean {
  return isQuotaErrorPayload({ message });
}

export function formatUsageSummary(
  usage: Usage,
  isPro: boolean,
  t: (key: string, opts?: Record<string, unknown>) => string,
): string {
  if (usage.remaining <= 0) {
    return isPro ? t("settings.usage_exhausted_pro") : t("settings.usage_exhausted");
  }
  const pct = Math.round(usageRemainingPercent(usage));
  return isPro ? t("settings.usage_left_pro", { pct }) : t("settings.usage_left", { pct });
}

export function quotaAlertTitle(isPro: boolean, t: (key: string) => string): string {
  return isPro ? t("chat.quota_title_pro") : t("chat.quota_title");
}

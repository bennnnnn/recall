import {
  formatUsageSummary,
  isQuotaErrorMessage,
  isQuotaErrorPayload,
  quotaAlertTitle,
  usageRemainingPercent,
  usageUsedPercent,
  usageUsedTokens,
} from "@/lib/quota";

describe("quota helpers", () => {
  const usage = {
    date: "2026-06-27",
    input_tokens: 1000,
    output_tokens: 2000,
    daily_limit: 30_000,
    used_tokens: 12_000,
    remaining: 18_000,
  };

  it("usageUsedTokens prefers authoritative used_tokens", () => {
    expect(usageUsedTokens(usage)).toBe(12_000);
    expect(
      usageUsedTokens({ ...usage, used_tokens: undefined, remaining: 5_000 }),
    ).toBe(25_000);
  });

  it("usageUsedPercent and usageRemainingPercent stay in sync", () => {
    expect(usageUsedPercent(usage)).toBe(40);
    expect(usageRemainingPercent(usage)).toBe(60);
  });

  it("detects structured and legacy quota errors", () => {
    expect(isQuotaErrorPayload({ code: "quota_exceeded" })).toBe(true);
    expect(isQuotaErrorMessage("You've used up today's free limit.")).toBe(true);
    expect(isQuotaErrorMessage("Network error")).toBe(false);
  });

  it("formatUsageSummary is plan-aware", () => {
    const t = (key: string, opts?: Record<string, unknown>) =>
      key === "settings.usage_left"
        ? `${opts?.pct}% free left`
        : key === "settings.usage_left_pro"
          ? `${opts?.pct}% pro left`
          : key;

    expect(formatUsageSummary(usage, false, t)).toBe("60% free left");
    expect(formatUsageSummary(usage, true, t)).toBe("60% pro left");
  });

  it("quotaAlertTitle is plan-aware", () => {
    const t = (key: string) => key;
    expect(quotaAlertTitle(false, t)).toBe("chat.quota_title");
    expect(quotaAlertTitle(true, t)).toBe("chat.quota_title_pro");
  });
});

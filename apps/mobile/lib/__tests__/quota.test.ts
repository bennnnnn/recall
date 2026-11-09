import {
  dayUsedPercent,
  formatUsageSummary,
  usageMessages,
  usageRemainingPercent,
  usageUsedPercent,
  usageUsedTokens,
} from "@/lib/quota";

describe("quota helpers", () => {
  const usage = {
    date: "2026-06-27",
    daily_limit: 100_000,
    used_tokens: 12_000,
    remaining: 88_000,
  };

  it("usageUsedTokens prefers authoritative used_tokens", () => {
    expect(usageUsedTokens(usage)).toBe(12_000);
    expect(
      usageUsedTokens({ ...usage, used_tokens: undefined, remaining: 5_000 }),
    ).toBe(95_000);
  });

  it("usageUsedPercent and usageRemainingPercent stay in sync", () => {
    expect(usageUsedPercent(usage)).toBe(12);
    expect(usageRemainingPercent(usage)).toBe(88);
  });

  it("formatUsageSummary is plan-aware", () => {
    const t = (key: string, opts?: Record<string, unknown>) =>
      key === "settings.usage_left"
        ? `${opts?.pct}% free left`
        : key === "settings.usage_left_paid"
          ? `${opts?.pct}% pro left`
          : key;

    expect(formatUsageSummary(usage, false, t)).toBe("88% free left");
    expect(formatUsageSummary(usage, true, t)).toBe("88% pro left");
  });

  it("counts the day's messages when the server sends them, and says how many are left", () => {
    const t = (key: string, opts?: Record<string, unknown>) => `${key} ${JSON.stringify(opts ?? {})}`;
    const counted = { ...usage, messages_used: 7, daily_messages: 10 };
    expect(usageMessages(counted)).toEqual({ used: 7, total: 10 });
    expect(formatUsageSummary(counted, false, t)).toBe('settings.usage_messages_left {"left":3,"total":10}');
    expect(formatUsageSummary({ ...counted, messages_used: 10 }, false, t)).toBe("settings.usage_exhausted {}");
    // A server that counts only tokens keeps the percentage.
    expect(usageMessages(usage)).toBeNull();
  });

  it("reads the day's share the same from GET /usage/today and from a turn's done", () => {
    // The nudge worked a turn's share out again by hand beside these helpers.
    const turn = { used_tokens: 12_000, daily_limit: 100_000, messages_used: 9, daily_messages: 10 };
    expect(dayUsedPercent(turn)).toBe(90);
    expect(dayUsedPercent({ ...usage, messages_used: 9, daily_messages: 10 })).toBe(90);
    expect(dayUsedPercent({ ...turn, messages_used: 14 })).toBe(100);
    expect(usageMessages({ ...turn, messages_used: 14 })).toEqual({ used: 10, total: 10 });
    // Tokens only: the share of the token budget, whole.
    expect(dayUsedPercent({ used_tokens: 12_345, daily_limit: 100_000 })).toBe(12);
    expect(dayUsedPercent(usage)).toBe(12);
  });
});

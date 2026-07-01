jest.mock("@/lib/api", () => ({
  api: { todayUsage: jest.fn() },
}));

import {
  QUOTA_NUDGE_THRESHOLD_PCT,
  shouldShowQuotaNudge,
} from "@/hooks/useQuotaNudge";

describe("shouldShowQuotaNudge", () => {
  it("shows for a free user at/above the threshold who hasn't dismissed today", () => {
    expect(shouldShowQuotaNudge(QUOTA_NUDGE_THRESHOLD_PCT, false, false)).toBe(true);
    expect(shouldShowQuotaNudge(95, false, false)).toBe(true);
  });

  it("does not show below the threshold", () => {
    expect(shouldShowQuotaNudge(QUOTA_NUDGE_THRESHOLD_PCT - 1, false, false)).toBe(false);
    expect(shouldShowQuotaNudge(0, false, false)).toBe(false);
  });

  it("never shows for pro users (they have a 500k limit)", () => {
    expect(shouldShowQuotaNudge(99, true, false)).toBe(false);
  });

  it("respects the per-day dismissal", () => {
    expect(shouldShowQuotaNudge(99, false, true)).toBe(false);
  });
});

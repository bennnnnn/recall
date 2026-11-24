import { hasPlanFeature, planNameKey, planOf, upgradeTargets } from "@/lib/plan";

describe("plan helpers", () => {
  it("treats anything unknown as free, never as paid", () => {
    expect(planOf(null)).toBe("free");
    expect(planOf({ plan: "enterprise" })).toBe("free");
    // The second paid plan is gone: a stale "plus" is no plan the app sells.
    expect(planOf({ plan: "plus" })).toBe("free");
    expect(planOf({ plan: "pro" })).toBe("pro");
  });

  it("reads features from the server when it lists them", () => {
    const user = { plan: "pro", features: ["speech_tts"] };
    expect(hasPlanFeature(user, "speech_tts")).toBe(true);
    expect(hasPlanFeature(user, "live_talk")).toBe(false);
    expect(hasPlanFeature(user, "all_models")).toBe(false);
  });

  it("falls back to each plan's defaults for an older cached user", () => {
    expect(hasPlanFeature({ plan: "free" }, "speech_transcription")).toBe(false);
    expect(hasPlanFeature({ plan: "free" }, "image_generation")).toBe(true);
    expect(hasPlanFeature({ plan: "pro" }, "speech_transcription")).toBe(true);
    expect(hasPlanFeature({ plan: "pro" }, "live_talk")).toBe(true);
  });

  it("offers Free the one paid plan, and the paid plan nothing", () => {
    expect(upgradeTargets("free")).toEqual(["pro"]);
    expect(upgradeTargets("pro")).toEqual([]);
  });

  it("keeps display names in i18n", () => {
    expect(planNameKey("pro")).toBe("plans.pro");
  });
});

import {
  homeLearningCardColors,
  homeLearningUrgency,
  learningProgressColors,
  mixHexColors,
} from "@/lib/homeLearningCard";

describe("homeLearningCard", () => {
  it("homeLearningUrgency is zero when goal is met", () => {
    expect(
      homeLearningUrgency({ completedToday: 10, dailyGoal: 10, hour: 21 }),
    ).toBe(0);
  });

  it("homeLearningUrgency stays low in the morning when behind", () => {
    const morning = homeLearningUrgency({
      completedToday: 0,
      dailyGoal: 10,
      hour: 8,
    });
    const evening = homeLearningUrgency({
      completedToday: 0,
      dailyGoal: 10,
      hour: 20,
    });
    expect(morning).toBeLessThan(0.2);
    expect(evening).toBeGreaterThan(0.6);
    expect(evening).toBeGreaterThan(morning);
  });

  it("homeLearningUrgency is lower when closer to the goal at the same hour", () => {
    const behind = homeLearningUrgency({
      completedToday: 1,
      dailyGoal: 10,
      hour: 19,
    });
    const almost = homeLearningUrgency({
      completedToday: 9,
      dailyGoal: 10,
      hour: 19,
    });
    expect(almost).toBeLessThan(behind);
  });

  it("mixHexColors blends toward the target", () => {
    expect(mixHexColors("#000000", "#FFFFFF", 0)).toBe("#000000");
    expect(mixHexColors("#000000", "#FFFFFF", 1)).toBe("#ffffff");
    expect(mixHexColors("#000000", "#FFFFFF", 0.5)).toBe("#808080");
  });

  it("homeLearningCardColors stays on brand primary (no danger shift)", () => {
    const calm = homeLearningCardColors({
      urgency: 0,
      surface: "#F4F4F4",
      primaryLight: "#E5F2FF",
      dangerLight: "#FEE2E2",
      primary: "#007AFF",
      danger: "#DC2626",
      success: false,
    });
    const hot = homeLearningCardColors({
      urgency: 1,
      surface: "#F4F4F4",
      primaryLight: "#E5F2FF",
      dangerLight: "#FEE2E2",
      primary: "#007AFF",
      danger: "#DC2626",
      success: false,
    });
    expect(calm.background.toLowerCase()).toBe("#e5f2ff");
    expect(hot.background.toLowerCase()).toBe("#e5f2ff");
    expect(hot.fill.toLowerCase()).toBe(calm.fill.toLowerCase());
    expect(hot.accent.toLowerCase()).toBe("#007aff");
  });

  it("learningProgressColors stays brand primary even when behind at night", () => {
    const colors = learningProgressColors({
      completedToday: 0,
      dailyGoal: 10,
      hour: 20,
      surface: "#F4F4F4",
      primaryLight: "#E5F2FF",
      dangerLight: "#FEE2E2",
      primary: "#007AFF",
      danger: "#DC2626",
    });
    expect(colors.background.toLowerCase()).toBe("#e5f2ff");
    expect(colors.accent.toLowerCase()).toBe("#007aff");
    expect(colors.accent.toLowerCase()).toBe(colors.fill.toLowerCase());
  });
});

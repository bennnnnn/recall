import { resolveColorScheme } from "@/lib/appearance";
import {
  getAppearancePreferenceSnapshot,
  resetAppearanceRuntimeForTest,
  setAppearancePreferenceSnapshot,
  subscribeAppearancePreference,
} from "@/lib/appearanceRuntime";

describe("appearanceRuntime", () => {
  beforeEach(() => {
    resetAppearanceRuntimeForTest();
  });

  it("notifies subscribers when preference changes", () => {
    const listener = jest.fn();
    const unsubscribe = subscribeAppearancePreference(listener);

    setAppearancePreferenceSnapshot("dark");
    expect(getAppearancePreferenceSnapshot()).toBe("dark");
    expect(listener).toHaveBeenCalledTimes(1);

    unsubscribe();
    setAppearancePreferenceSnapshot("light");
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("resolveColorScheme uses stored preference", () => {
    setAppearancePreferenceSnapshot("dark");
    expect(resolveColorScheme("light", getAppearancePreferenceSnapshot())).toBe("dark");
  });
});

import { shadowElevated, shadowOverlay, shadowRaised } from "@/lib/shadow";
import { darkTheme, lightTheme } from "@/lib/theme";

describe("shadowRaised", () => {
  it("uses a lighter opacity in light mode than dark", () => {
    const light = shadowRaised(lightTheme);
    const dark = shadowRaised(darkTheme);
    expect(light.shadowOpacity).toBeLessThan(dark.shadowOpacity as number);
  });
});

describe("shadowOverlay", () => {
  it("keeps stronger elevation for menus", () => {
    expect(shadowOverlay(lightTheme).elevation).toBe(20);
    expect(shadowOverlay(darkTheme).shadowOpacity).toBeGreaterThan(
      shadowRaised(darkTheme).shadowOpacity as number,
    );
  });
});

describe("shadowElevated", () => {
  it("scales opacity by theme for floating chrome", () => {
    const light = shadowElevated(lightTheme, "fab");
    const dark = shadowElevated(darkTheme, "fab");
    expect(light.elevation).toBe(8);
    expect(light.shadowOpacity).toBeLessThan(dark.shadowOpacity as number);
  });
});

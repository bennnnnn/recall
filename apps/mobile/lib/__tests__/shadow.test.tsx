import { boxShadowElevated, shadowOverlay, shadowRaised } from "@/lib/shadow";
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

describe("boxShadowElevated", () => {
  it("embeds scrim alpha instead of raw black", () => {
    const fab = boxShadowElevated(lightTheme, "fab");
    expect(fab.boxShadow).toContain("rgba");
    expect(fab.elevation).toBe(8);
  });
});

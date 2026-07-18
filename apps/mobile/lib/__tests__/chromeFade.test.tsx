import { bottomChromeFadeColors, topChromeFadeColors } from "@/lib/chromeFade";
import { darkTheme, lightTheme, withAlpha } from "@/lib/theme";

describe("chromeFade", () => {
  it("BUG FIX regression: every stop is a valid rgba()/solid color for both themes", () => {
    // The old implementation string-concatenated a hex alpha suffix onto
    // theme.bg (`${theme.bg}FA`) — only valid because theme.bg happens to be
    // 6-digit hex today. Assert the output is always a real color, not a
    // format-specific special case.
    for (const theme of [lightTheme, darkTheme]) {
      for (const stop of [...topChromeFadeColors(theme), ...bottomChromeFadeColors(theme)]) {
        expect(stop === theme.bg || /^rgba\(\d+, \d+, \d+, [\d.]+\)$/.test(stop)).toBe(true);
      }
    }
  });

  it("top fade starts solid and ends fully transparent", () => {
    const stops = topChromeFadeColors(lightTheme);
    expect(stops[0]).toBe(lightTheme.bg);
    expect(stops[stops.length - 1]).toBe(withAlpha(lightTheme.bg, 0));
  });

  it("bottom fade starts fully transparent and ends solid", () => {
    const stops = bottomChromeFadeColors(darkTheme);
    expect(stops[0]).toBe(withAlpha(darkTheme.bg, 0));
    expect(stops[stops.length - 1]).toBe(darkTheme.bg);
  });

  it("light and dark use the same alpha curve (only the base color differs)", () => {
    const lightTop = topChromeFadeColors(lightTheme).map((c) => c.match(/[\d.]+\)$/)?.[0]);
    const darkTop = topChromeFadeColors(darkTheme).map((c) => c.match(/[\d.]+\)$/)?.[0]);
    expect(darkTop.slice(1)).toEqual(lightTop.slice(1));
  });
});

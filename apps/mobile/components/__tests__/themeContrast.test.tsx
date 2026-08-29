import { darkTheme, lightTheme } from "@/lib/theme";

/** WCAG 2.x relative luminance (sRGB). */
function relativeLuminance(hex: string): number {
  const raw = hex.replace("#", "");
  const n = parseInt(raw, 16);
  const channels = [n >> 16, (n >> 8) & 0xff, n & 0xff].map((c) => {
    const s = c / 255;
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

function contrastRatio(fg: string, bg: string): number {
  const a = relativeLuminance(fg);
  const b = relativeLuminance(bg);
  const hi = Math.max(a, b);
  const lo = Math.min(a, b);
  return (hi + 0.05) / (lo + 0.05);
}

const AA = 4.5;

describe("semantic text contrast", () => {
  it.each([
    ["light", lightTheme],
    ["dark", darkTheme],
  ] as const)("%s textTertiary is AA on bg and surfaceAlt", (_name, theme) => {
    expect(contrastRatio(theme.textTertiary, theme.bg)).toBeGreaterThanOrEqual(AA);
    expect(contrastRatio(theme.textTertiary, theme.surfaceAlt)).toBeGreaterThanOrEqual(AA);
  });

  it.each([
    ["light", lightTheme],
    ["dark", darkTheme],
  ] as const)("%s textSecondary is AA on surfaceAlt", (_name, theme) => {
    expect(contrastRatio(theme.textSecondary, theme.surfaceAlt)).toBeGreaterThanOrEqual(AA);
  });

  it("textDisabled may sit below AA (placeholders / decoration only)", () => {
    expect(contrastRatio(lightTheme.textDisabled, lightTheme.surfaceAlt)).toBeLessThan(AA);
    expect(contrastRatio(darkTheme.textDisabled, darkTheme.surfaceAlt)).toBeLessThan(AA);
  });
});

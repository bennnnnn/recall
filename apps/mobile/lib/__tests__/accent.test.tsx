import {
  ACCENT_OPTIONS,
  ACCENTS,
  DEFAULT_ACCENT,
  normalizeAccentPreference,
  type AccentPreference,
} from "@/lib/accent";
import { Text } from "react-native";
import { render } from "@testing-library/react-native";

import { BrandAccent, setAccentSnapshot } from "@/lib/accentRuntime";
import { applyAccent, darkTheme, lightTheme, themeFor, useTheme } from "@/lib/theme";
import { colorDifference } from "@/lib/__tests__/support/colorDifference";

/** WCAG 2.1 relative luminance of a #RRGGBB color. */
function luminance(hex: string): number {
  const channels = [1, 3, 5].map((start) => parseInt(hex.slice(start, start + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const SCHEMES = [lightTheme, darkTheme];

describe("accent presets", () => {
  it.each(ACCENT_OPTIONS)("%s keeps links, buttons and the user bubble readable", (accent) => {
    for (const base of SCHEMES) {
      const theme = applyAccent(base, accent);
      // Links and selected text on the page and on cards.
      expect(contrast(theme.primary, theme.bg)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(theme.primary, theme.surface)).toBeGreaterThanOrEqual(4.5);
      // ...in a pressed well, a menu and a Settings group.
      expect(contrast(theme.primary, theme.surfaceAlt)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(theme.primary, theme.elevated)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(theme.primary, theme.settingsSurface)).toBeGreaterThanOrEqual(4.5);
      // Button labels on a primary fill, also when pressed.
      expect(contrast(theme.onPrimary, theme.primary)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(theme.onPrimary, theme.primaryDark)).toBeGreaterThanOrEqual(4.5);
      // The user's own messages.
      expect(contrast(theme.userText, theme.userBubble)).toBeGreaterThanOrEqual(7);
      // Selected text on a soft accent well: plain ink and accent ink (a selected chip).
      expect(contrast(theme.text, theme.primaryLight)).toBeGreaterThanOrEqual(7);
      expect(contrast(theme.primary, theme.primaryLight)).toBeGreaterThanOrEqual(4.5);
    }
  });

  // A green, pink or brown accent is welcome; one a reader takes for a done check, an
  // overdue time or a warning is not. The theme's own danger and warning sit 10.7 apart.
  it.each(ACCENT_OPTIONS)("%s never reads as success, warning or danger", (accent) => {
    for (const base of SCHEMES) {
      const { primary } = applyAccent(base, accent);
      const apart = (["success", "warning", "danger"] as const).map((status) => ({
        status,
        clear: colorDifference(primary, base[status]) >= 12,
      }));
      expect({ scheme: base.scheme, apart }).toEqual({
        scheme: base.scheme,
        apart: apart.map(({ status }) => ({ status, clear: true })),
      });
    }
  });

  it("measures color difference as a reader sees it", () => {
    expect(colorDifference("#FFFFFF", "#000000")).toBeCloseTo(100, 0);
    expect(colorDifference("#137A54", "#137A54")).toBe(0);
    // Two greens a reader tells apart, and two blues one step apart in the picker.
    expect(colorDifference("#137A54", "#2A6C02")).toBeGreaterThan(12);
    expect(colorDifference("#4F56E5", "#1661C3")).toBeLessThan(12);
  });

  it("indigo is the default and leaves the palette exactly as it was", () => {
    expect(DEFAULT_ACCENT).toBe("indigo");
    expect(themeFor("light", "indigo")).toBe(lightTheme);
    expect(themeFor("dark", "indigo")).toBe(darkTheme);
    for (const base of SCHEMES) {
      expect(applyAccent(base, "indigo")).toEqual(base);
    }
  });

  it("an accent fills every brand slot and nothing else", () => {
    for (const accent of ACCENT_OPTIONS) {
      for (const base of SCHEMES) {
        const theme = applyAccent(base, accent);
        const tones = ACCENTS[accent][base.scheme];
        expect(theme.accent).toBe(tones.primary);
        expect(theme.accentLight).toBe(tones.primaryLight);
        expect(theme.accentDark).toBe(tones.primaryDark);
        expect(theme.graphSeries).toEqual([
          tones.primary,
          "series2" in tones ? tones.series2 : base.graphSeries[1],
          "series3" in tones ? tones.series3 : base.graphSeries[2],
          "series4" in tones ? tones.series4 : base.graphSeries[3],
        ]);
        expect(theme.success).toBe(base.success);
        expect(theme.danger).toBe(base.danger);
        expect(theme.text).toBe(base.text);
      }
    }
  });

  it("one theme object per scheme and accent, so cached styles stay valid", () => {
    for (const accent of ACCENT_OPTIONS) {
      expect(themeFor("light", accent)).toBe(themeFor("light", accent));
      expect(themeFor("dark", accent)).toBe(themeFor("dark", accent));
    }
  });

  it("an unknown or missing stored value falls back to indigo", () => {
    expect(normalizeAccentPreference(null)).toBe("indigo");
    expect(normalizeAccentPreference("chartreuse")).toBe("indigo");
    expect(normalizeAccentPreference("__proto__")).toBe("indigo");
    for (const accent of ACCENT_OPTIONS) {
      expect(normalizeAccentPreference(accent)).toBe<AccentPreference>(accent);
    }
  });
});

describe("BrandAccent", () => {
  afterEach(() => setAccentSnapshot(DEFAULT_ACCENT));

  function Swatch() {
    return <Text>{useTheme().primary}</Text>;
  }

  it("keeps the screens before sign-in indigo when the phone picked another accent", async () => {
    // Live, 2026-11-07: a Berry pick turned the landing pink.
    setAccentSnapshot("berry");
    const { getAllByText } = await render(
      <>
        <BrandAccent>
          <Swatch />
        </BrandAccent>
        <Swatch />
      </>,
    );
    expect(getAllByText(lightTheme.primary)).toHaveLength(1);
    expect(getAllByText(applyAccent(lightTheme, "berry").primary)).toHaveLength(1);
  });
});

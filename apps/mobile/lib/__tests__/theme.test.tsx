import { darkTheme, lightTheme, withAlpha } from "@/lib/theme";

describe("surface hierarchy", () => {
  it("keeps the canvas a step below raised white/surface so chrome can float", () => {
    expect(lightTheme.bg).not.toBe(lightTheme.surface);
    expect(lightTheme.bg).toBe(lightTheme.composerBg);
    expect(lightTheme.inputBg).toBe(lightTheme.surface);
    expect(darkTheme.bg).not.toBe(darkTheme.surface);
    expect(darkTheme.inputBg).toBe(darkTheme.surface);
  });
});

describe("withAlpha", () => {
  it("converts a 6-digit hex color to rgba with the given alpha", () => {
    expect(withAlpha("#2563EB", 0.5)).toBe("rgba(37, 99, 235, 0.5)");
  });

  it("expands a 3-digit hex color before converting", () => {
    expect(withAlpha("#fff", 1)).toBe("rgba(255, 255, 255, 1)");
  });

  it("replaces the alpha channel of an existing rgba(...) color", () => {
    expect(withAlpha("rgba(0,0,0,0.40)", 0.1)).toBe("rgba(0, 0, 0, 0.1)");
  });

  it("adds an alpha channel to a plain rgb(...) color", () => {
    expect(withAlpha("rgb(74, 222, 128)", 0.16)).toBe("rgba(74, 222, 128, 0.16)");
  });

  it("BUG FIX regression: does not mangle a color it can't parse", () => {
    // The old pattern (`${color}FA` string concatenation) silently produced
    // an invalid color string for anything not already a 6-digit hex — e.g.
    // theme.scrim and dark mode's successLight are already rgba(...) with a
    // 3-digit-alpha-suffix-unsafe shape once further suffixed. withAlpha
    // must degrade to "leave it alone" instead of emitting garbage.
    expect(withAlpha("hsl(210, 90%, 55%)", 0.5)).toBe("hsl(210, 90%, 55%)");
  });

  it("clamps alpha to [0, 1]", () => {
    expect(withAlpha("#000000", 5)).toBe("rgba(0, 0, 0, 1)");
    expect(withAlpha("#000000", -5)).toBe("rgba(0, 0, 0, 0)");
  });

  it("every hex token in both palettes round-trips through withAlpha without throwing", () => {
    for (const theme of [lightTheme, darkTheme]) {
      for (const [key, value] of Object.entries(theme)) {
        if (typeof value !== "string" || !value.startsWith("#")) continue;
        expect(() => withAlpha(value, 0.5)).not.toThrow();
        expect(withAlpha(value, 0.5)).toMatch(/^rgba\(\d+, \d+, \d+, 0\.5\)$/);
        void key;
      }
    }
  });
});

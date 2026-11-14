/**
 * Canvas labels across fonts: SpaceMono has no Greek, so "τ = 15 N·m" lost
 * its τ until a label could fall back to the math faces.
 */
import type { SkFont } from "@shopify/react-native-skia";

import {
  fontRuns,
  measureRuns,
  needsFallback,
  needsTabular,
  SCRIPT_SCALE,
  tabularGlyphs,
} from "@/components/rich/skia/fontRuns";

/** A stand-in font: draws `chars`, each `advance` wide (or as `widths` says); glyph 0 is "missing". */
function fakeFont(chars: string, advance: number, widths: Record<string, number> = {}): SkFont {
  const font = {
    getGlyphIDs: (text: string) =>
      Array.from(text).map((char) => (chars.includes(char) ? char.codePointAt(0)! : 0)),
    getGlyphWidths: (ids: number[]) => ids.map((id) => widths[String.fromCodePoint(id)] ?? advance),
    measureText: (text: string) => ({ x: 0, y: 0, width: Array.from(text).length * advance, height: 11 }),
  };
  return font as unknown as SkFont;
}

const mono = fakeFont("= 15N·mFabc", 6);
const greek = fakeFont("τθλΩ", 5);

describe("fontRuns", () => {
  it("sets a character the first font lacks in the next one that has it", () => {
    const runs = fontRuns("τ = 15 N·m", [mono, greek]);
    expect(runs.map((run) => [run.text, run.font === greek, run.dx])).toEqual([
      ["τ", true, 0],
      [" = 15 N·m", false, 5],
    ]);
  });

  it("keeps a label the first font can draw as one run, measured as before", () => {
    expect(needsFallback("F = 15 N", [mono, greek])).toBe(false);
    expect(fontRuns("F = 15 N", [mono, greek])).toHaveLength(1);
    expect(measureRuns("F = 15 N", [mono, greek])).toBe(48);
  });

  it("measures a mixed label run by run", () => {
    expect(needsFallback("Ω", [mono, greek])).toBe(true);
    expect(measureRuns("R = 4 Ω", [mono, greek])).toBe(6 * 6 + 5);
  });

  it("leaves a character no font has in the first font", () => {
    const runs = fontRuns("a☃b", [mono, greek]);
    expect(runs).toHaveLength(1);
    expect(runs[0].font).toBe(mono);
  });
});

// The system face draws "1" narrower than "0": axis numbers in a column no longer lined up
// once the figures left the monospace face.
describe("tabular digits", () => {
  const proportional = fakeFont("0123456789.", 6, { "1": 4, ".": 3 });

  it("sets each digit of a proportional face in the widest digit's cell", () => {
    const { glyphs, width } = tabularGlyphs(proportional, "10.5");
    expect(glyphs.map((glyph) => glyph.pos.x)).toEqual([1, 6, 12, 15]);
    expect(width).toBe(21);
    expect(measureRuns("10.5", [proportional])).toBe(21);
    expect(needsTabular(proportional, "10.5")).toBe(true);
  });

  it("measures nothing while a label's face has not loaded", () => {
    expect(measureRuns("10.5", [null, mono])).toBe(0);
  });

  it("leaves a face whose digits are one width, and a label with no digits, as text", () => {
    expect(needsTabular(mono, "F = 15 N")).toBe(false);
    expect(needsTabular(proportional, "m/s")).toBe(false);
  });
});


// The diagrams' face has the digit scripts (R₁) but no letter ones: the lens diagram's
// "dₒ = 30 cm" drew a missing-glyph box where its o belonged.
describe("a script letter no face has", () => {
  const sans = fakeFont("Rdo =30cm₁", 6);

  it("is its letter, set small and lowered, and measured so", () => {
    const runs = fontRuns("dₒ = 30 cm", [sans]);
    expect(runs.map((run) => [run.text, run.script ?? null, run.dx])).toEqual([
      ["d", null, 0],
      ["o", "sub", 6],
      [" = 30 cm", null, 6 + 6 * SCRIPT_SCALE],
    ]);
    expect(needsFallback("dₒ = 30 cm", [sans])).toBe(true);
    expect(measureRuns("dₒ", [sans])).toBeCloseTo(6 + 6 * SCRIPT_SCALE);
  });

  it("leaves a script glyph the face has as text", () => {
    expect(needsFallback("R₁ = 30", [sans])).toBe(false);
  });
});

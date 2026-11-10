/**
 * Canvas text across more than one font, its numbers tabular.
 *
 * A Skia font draws nothing for a character it has no glyph for: when the
 * figures' labels were set in SpaceMono, "τ = 15 N·m" came out as "= 15 N·m".
 * A label is split into runs, each in the first font that can draw it, and the
 * runs are set side by side.
 *
 * A Skia font cannot ask for a face's tabular figures (the UI's text does, with
 * `fontVariant`), and the system face's digits are proportional. In such a face
 * each digit is set in one cell, the widest digit's advance, so a column of
 * numbers lines up; a face whose digits are one width already is drawn as is.
 */
import type { Glyph, SkFont } from "@shopify/react-native-skia";

import { scriptGlyphBase } from "@/lib/unicodeSupSub";

/**
 * `script`: the run is a sub- or superscript drawn from its letters (`ₒ` from "o"), small and
 * off the line, because no face has the script glyph.
 */
export type FontRun = { text: string; font: SkFont; dx: number; script?: "sub" | "sup" };

/**
 * A script's size beside its line, as the maths draws one (`SCRIPT_RATIO`, 0.7). The figures'
 * faces have digit scripts (R₁) but no letter ones: "dₒ = 30 cm" showed a missing-glyph box.
 */
export const SCRIPT_SCALE = 0.7;

const DIGIT = /^[0-9]$/;
const digitCells = new WeakMap<SkFont, { cell: number; varies: boolean }>();

/** The widest digit's advance in `font` (the cell every digit is set in), and whether they differ. */
function digitCell(font: SkFont): { cell: number; varies: boolean } {
  let digits = digitCells.get(font);
  if (digits === undefined) {
    const widths = font.getGlyphWidths(font.getGlyphIDs("0123456789"));
    const cell = Math.max(0, ...widths);
    digits = { cell, varies: widths.some((width) => cell - width > 0.01) };
    digitCells.set(font, digits);
  }
  return digits;
}

/** Whether `text` has digits `font` draws at different widths: they are then set in cells. */
export function needsTabular(font: SkFont, text: string): boolean {
  return /[0-9]/.test(text) && digitCell(font).varies;
}

/** `text`'s glyphs in `font` placed from 0, each digit centred in its cell, and their width. */
export function tabularGlyphs(font: SkFont, text: string): { glyphs: Glyph[]; width: number } {
  const chars = Array.from(text);
  const ids = font.getGlyphIDs(text);
  const widths = font.getGlyphWidths(ids);
  const cell = chars.some((char) => DIGIT.test(char)) ? digitCell(font).cell : 0;
  let x = 0;
  const glyphs = ids.map((id, at) => {
    const own = widths[at] ?? 0;
    const advance = DIGIT.test(chars[at] ?? "") ? cell : own;
    const glyph = { id, pos: { x: x + (advance - own) / 2, y: 0 } };
    x += advance;
    return glyph;
  });
  return { glyphs, width: x };
}

function hasGlyph(font: SkFont, char: string): boolean {
  const ids = font.getGlyphIDs(char);
  return ids.length > 0 && ids[0] !== 0;
}

/**
 * `text` as runs, each in the first of `fonts` that has every glyph in it
 * (the first font when none does), with each run's offset from the start.
 */
export function fontRuns(text: string, fonts: readonly SkFont[]): FontRun[] {
  const runs: FontRun[] = [];
  if (fonts.length === 0) return runs;
  for (const char of Array.from(text)) {
    const own = fonts.find((candidate) => hasGlyph(candidate, char));
    // A script glyph no face has is its letter, set as a script: never a missing glyph.
    const script = own ? null : scriptGlyphBase(char);
    const drawn = script ? script.base : char;
    const font = own ?? fonts.find((candidate) => hasGlyph(candidate, drawn)) ?? fonts[0];
    const last = runs[runs.length - 1];
    if (last && last.font === font && last.script === script?.kind) last.text += drawn;
    else runs.push({ text: drawn, font, dx: 0, ...(script ? { script: script.kind } : {}) });
  }
  let dx = 0;
  for (const run of runs) {
    run.dx = dx;
    dx += runWidth(run);
  }
  return runs;
}

/** A run's advance: a script's letters at the script's size. */
function runWidth(run: FontRun): number {
  return tabularGlyphs(run.font, run.text).width * (run.script ? SCRIPT_SCALE : 1);
}

/** Whether `text` needs more than its first font, or a script drawn from its letters. */
export function needsFallback(text: string, fonts: readonly SkFont[]): boolean {
  const runs = fontRuns(text, fonts);
  return runs.length > 1 || (runs.length === 1 && (runs[0].font !== fonts[0] || Boolean(runs[0].script)));
}

/** The width a label takes, as `HaloText` sets it; nothing while its face has not loaded. */
export function measureRuns(text: string, given: readonly (SkFont | null)[]): number {
  const fonts = given.filter((font): font is SkFont => font !== null);
  if (fonts.length === 0 || given[0] === null) return 0;
  if (!needsFallback(text, fonts)) return tabularGlyphs(fonts[0], text).width;
  const runs = fontRuns(text, fonts);
  const last = runs[runs.length - 1];
  return last.dx + runWidth(last);
}

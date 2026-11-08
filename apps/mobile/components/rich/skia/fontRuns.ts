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

type FontRun = { text: string; font: SkFont; dx: number };

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
    const font = fonts.find((candidate) => hasGlyph(candidate, char)) ?? fonts[0];
    const last = runs[runs.length - 1];
    if (last && last.font === font) last.text += char;
    else runs.push({ text: char, font, dx: 0 });
  }
  let dx = 0;
  for (const run of runs) {
    run.dx = dx;
    dx += tabularGlyphs(run.font, run.text).width;
  }
  return runs;
}

/** Whether `text` needs more than its first font. */
export function needsFallback(text: string, fonts: readonly SkFont[]): boolean {
  const runs = fontRuns(text, fonts);
  return runs.length > 1 || (runs.length === 1 && runs[0].font !== fonts[0]);
}

/** The width a label takes, as `HaloText` sets it. */
export function measureRuns(text: string, fonts: readonly SkFont[]): number {
  if (fonts.length === 0) return 0;
  if (!needsFallback(text, fonts)) return tabularGlyphs(fonts[0], text).width;
  const runs = fontRuns(text, fonts);
  const last = runs[runs.length - 1];
  return last.dx + tabularGlyphs(last.font, last.text).width;
}

/**
 * Column widths for a markdown table, from the text each column holds.
 *
 * A column is as wide as its longest cell asks for, between a floor (its
 * longest word, so a word never breaks mid-letter) and a ceiling (so a long
 * description wraps instead of taking the screen). A short label column
 * therefore stays narrow beside a long one. A table that fits the viewport is
 * stretched to fill it; a wider one keeps its widths and pans, with the next
 * column's start showing at the edge so it reads as one that scrolls.
 */
import { type AstNode, astSource, astText } from "@/components/markdown/markdownAstHelpers";
import { Space } from "@/lib/space";

/**
 * What one column holds, in Latin letters' widths: a Latin letter is 1, a CJK or
 * Ethiopic character about 2 (each is near square, about the type's size), a combining
 * mark 0. Counting characters gave an Amharic or Chinese cell half the room it needed,
 * so its words broke mid-letter.
 */
export type TableColumnText = { longest: number; longestWord: number };

/** Mean advance of a Latin letter in the 15 pt cell face, rounded up so estimates err wide. */
const CHAR_WIDTH = 8;
/** The cell's horizontal padding (`cellInner`), both sides. */
const CELL_PAD = Space.sm * 2;
export const TABLE_MIN_COL_WIDTH = 72;
export const TABLE_MAX_COL_WIDTH = 240;

/** Scripts whose characters are about as wide as the type is tall. */
const WIDE_CHAR =
  /[ᄀ-ᅟሀ-᎟ⶀ-⷟⺀-〾ぁ-㏿㐀-䶿一-鿿ꀀ-꓏꬀-꬯가-힣豈-﫿︰-﹏＀-｠￠-￦\u{1E7E0}-\u{1E7FF}\u{20000}-\u{3FFFD}]/u;
/** Han, kana and Hangul lines break between any two characters, as words do at spaces. */
const BREAKS_ANYWHERE = /[⺀-〾ぁ-㏿㐀-䶿一-鿿가-힣豈-﫿\u{20000}-\u{3FFFD}]/u;
const MARK = /\p{M}/u;
const EMOJI = /\p{Extended_Pictographic}/u;

/** One character's width in Latin letters. */
function charUnits(char: string): number {
  if (MARK.test(char) || char === "‍" || char === "️") return 0;
  if (EMOJI.test(char)) return 2.5;
  return WIDE_CHAR.test(char) ? 2 : 1;
}

/** A cell's text: its whole width and its widest unbreakable run, in Latin letters' widths. */
export function textWidthUnits(text: string): { width: number; longestWord: number } {
  let width = 0;
  let word = 0;
  let longestWord = 0;
  for (const char of text) {
    const units = charUnits(char);
    width += units;
    if (/\s/.test(char)) {
      word = 0;
    } else if (BREAKS_ANYWHERE.test(char)) {
      word = 0;
      longestWord = Math.max(longestWord, units);
    } else {
      word += units;
      longestWord = Math.max(longestWord, word);
    }
  }
  return { width, longestWord };
}

/** Each column's longest cell and longest word, header included. */
export function tableColumnText(node: AstNode): TableColumnText[] {
  const columns: TableColumnText[] = [];
  const walk = (n: AstNode) => {
    if (n.type === "tr") {
      const cells = (n.children ?? []).filter((c) => c.type === "th" || c.type === "td");
      cells.forEach((cell, index) => {
        const { width, longestWord } = textWidthUnits(astText(cell).trim());
        const column = columns[index] ?? { longest: 0, longestWord: 0 };
        column.longest = Math.max(column.longest, width);
        column.longestWord = Math.max(column.longestWord, longestWord);
        columns[index] = column;
      });
      return;
    }
    (n.children ?? []).forEach(walk);
  };
  walk(node);
  return columns.length > 0 ? columns : [{ longest: 0, longestWord: 0 }];
}

/**
 * What a table row is drawn from: its cells' AST and the kinds of block it
 * sits in. Two rows with the same source draw the same. Null inside a
 * blockquote, whose text style reads the whole quote (`inPlainBlockquote`).
 */
export function tableRowSource(row: AstNode, parents: AstNode[]): string | null {
  if (parents.some((parent) => parent.type === "blockquote")) return null;
  return `${parents.map((parent) => parent.type).join(">")}|${astSource(row)}`;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/**
 * How the phone's text size sizes a column: a letter grows with it (`fontScale`), and so
 * may the widest column, up to the viewport, so a long word at a large size still fits.
 */
type TableScale = { charWidth: number; maxWidth: number };

function tableScale(fontScale: number, viewportWidth: number): TableScale {
  const scale = Math.max(1, fontScale);
  return {
    charWidth: CHAR_WIDTH * scale,
    maxWidth: Math.max(TABLE_MAX_COL_WIDTH, Math.min(TABLE_MAX_COL_WIDTH * scale, viewportWidth)),
  };
}

/** The narrowest a column draws: its longest word, so a word never breaks mid-letter. */
function tableColumnFloor({ longestWord }: TableColumnText, { charWidth, maxWidth }: TableScale): number {
  return clamp(longestWord * charWidth + CELL_PAD, TABLE_MIN_COL_WIDTH, maxWidth);
}

/** The width one column asks for before the table is fitted to the viewport. */
function tableColumnNaturalWidth(column: TableColumnText, scale: TableScale): number {
  return clamp(column.longest * scale.charWidth + CELL_PAD, tableColumnFloor(column, scale), scale.maxWidth);
}

/** How much of the next column a wide table shows at the viewport's edge. */
export const TABLE_PEEK = 48;

/**
 * A wide table whose edge falls inside a column showed no hint of the columns after
 * it: "Mitosis | Meiosis" showed Mitosis cut at the edge and no Meiosis at all. The
 * column the edge cuts narrows, never below its floor, until the next one peeks in.
 */
function withNextColumnShowing(widths: number[], floors: number[], viewportWidth: number): number[] {
  const edge = viewportWidth - TABLE_PEEK;
  let start = 0;
  for (let index = 0; index < widths.length - 1; index += 1) {
    const width = widths[index]!;
    if (start + width > edge) {
      const room = Math.floor(edge - start);
      if (room >= floors[index]! && room < width) return widths.map((w, i) => (i === index ? room : w));
      return widths;
    }
    start += width;
  }
  return widths;
}

/**
 * Pixel widths for every column. When the natural widths fit, the spare room
 * is shared in proportion so the table spans the viewport; otherwise they
 * stay as they are and the table scrolls sideways. `fontScale` is the phone's text size
 * (`useWindowDimensions().fontScale`), which the cells' text follows.
 */
export function tableColumnWidths(columns: TableColumnText[], viewportWidth: number, fontScale = 1): number[] {
  const scale = tableScale(fontScale, viewportWidth);
  const natural = columns.map((column) => tableColumnNaturalWidth(column, scale));
  const total = natural.reduce((sum, w) => sum + w, 0);
  if (total >= viewportWidth) {
    const floors = columns.map((column) => tableColumnFloor(column, scale));
    return withNextColumnShowing(natural, floors, viewportWidth);
  }
  const stretch = viewportWidth / total;
  return natural.map((w) => Math.floor(w * stretch));
}

export function sumWidths(widths: number[]): number {
  return widths.reduce((sum, w) => sum + w, 0);
}

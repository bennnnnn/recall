/**
 * Column widths for a markdown table, from the text each column holds.
 *
 * A column is as wide as its longest cell asks for, between a floor (its
 * longest word, so a word never breaks mid-letter) and a ceiling (so a long
 * description wraps instead of taking the screen). A short label column
 * therefore stays narrow beside a long one. A table that fits the viewport is
 * stretched to fill it; a wider one keeps its widths and pans.
 */
import { type AstNode, astText } from "@/components/markdown/markdownAstHelpers";
import { Space } from "@/lib/space";

/** What one column holds, in characters. */
export type TableColumnText = { longest: number; longestWord: number };

/** Mean advance of the 15 pt cell face, rounded up so estimates err wide. */
const CHAR_WIDTH = 8;
/** The cell's horizontal padding (`cellInner`), both sides. */
const CELL_PAD = Space.sm * 2;
export const TABLE_MIN_COL_WIDTH = 72;
export const TABLE_MAX_COL_WIDTH = 240;

/** Each column's longest cell and longest word, header included. */
export function tableColumnText(node: AstNode): TableColumnText[] {
  const columns: TableColumnText[] = [];
  const walk = (n: AstNode) => {
    if (n.type === "tr") {
      const cells = (n.children ?? []).filter((c) => c.type === "th" || c.type === "td");
      cells.forEach((cell, index) => {
        const text = astText(cell).trim();
        const word = text.split(/\s+/).reduce((max, w) => Math.max(max, w.length), 0);
        const column = columns[index] ?? { longest: 0, longestWord: 0 };
        column.longest = Math.max(column.longest, text.length);
        column.longestWord = Math.max(column.longestWord, word);
        columns[index] = column;
      });
      return;
    }
    (n.children ?? []).forEach(walk);
  };
  walk(node);
  return columns.length > 0 ? columns : [{ longest: 0, longestWord: 0 }];
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/** The width one column asks for before the table is fitted to the viewport. */
export function tableColumnNaturalWidth({ longest, longestWord }: TableColumnText): number {
  const floor = clamp(longestWord * CHAR_WIDTH + CELL_PAD, TABLE_MIN_COL_WIDTH, TABLE_MAX_COL_WIDTH);
  return clamp(longest * CHAR_WIDTH + CELL_PAD, floor, TABLE_MAX_COL_WIDTH);
}

/**
 * Pixel widths for every column. When the natural widths fit, the spare room
 * is shared in proportion so the table spans the viewport; otherwise they
 * stay as they are and the table scrolls sideways.
 */
export function tableColumnWidths(columns: TableColumnText[], viewportWidth: number): number[] {
  const natural = columns.map(tableColumnNaturalWidth);
  const total = natural.reduce((sum, w) => sum + w, 0);
  if (total >= viewportWidth) return natural;
  const scale = viewportWidth / total;
  return natural.map((w) => Math.floor(w * scale));
}

export function sumWidths(widths: number[]): number {
  return widths.reduce((sum, w) => sum + w, 0);
}

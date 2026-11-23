/**
 * Link reference definitions in a streaming reply's pieces (`streamBlocks.ts`).
 *
 * Each piece is its own markdown-it parse, and a reference (`[text][1]`,
 * `[1]`) resolves only in the parse that holds its definition
 * (`[1]: https://…`). So the pieces from the first one that uses or defines a
 * label to the last one are drawn as one; the pieces before and after them
 * hold none of those labels and draw the same apart. A line that only looks
 * like a definition ("[Note]: see below") defines nothing and ties nothing.
 */
import { markdownItInstance } from "@/lib/markdown/parser";

/** The labels a piece defines and the bracketed labels it holds, as markdown-it normalizes them. */
export type PieceRefs = { defines: string[]; mentions: string[] };

export const NO_REFS: PieceRefs = { defines: [], mentions: [] };

const BRACKETED_RE = /\[([^[\]]{1,999})\]/g;
/** A definition runs to the next blank line (a title may span lines); read at most this many. */
const DEFINITION_LINES = 20;

const normalize = (label: string) => markdownItInstance.utils.normalizeReference(label);

/** The labels the definition starting at `at` defines, as markdown-it reads it. */
function definedLabels(text: string, at: number): string[] {
  let end = at;
  for (let line = 0; line < DEFINITION_LINES && end < text.length; line += 1) {
    const nl = text.indexOf("\n", end);
    const next = nl < 0 ? text.length : nl + 1;
    if (line > 0 && text.slice(end, next).trim() === "") break;
    end = next;
  }
  const env: Parameters<typeof markdownItInstance.parse>[1] = {};
  markdownItInstance.block.parse(text.slice(at, end), markdownItInstance, env, []);
  return Object.keys(env.references ?? {});
}

/** Every bracketed run in `text`: any of them may be a reference's label. */
function mentionedLabels(text: string): string[] {
  if (!text.includes("]")) return [];
  const labels = new Set<string>();
  for (const match of text.matchAll(BRACKETED_RE)) {
    const label = normalize(match[1] ?? "");
    if (label) labels.add(label);
  }
  return [...labels];
}

/** The refs of `text`, whose definitions start at `definitions`. */
export function pieceRefs(text: string, definitions: number[], offset: number): PieceRefs {
  const defines = definitions.flatMap((at) => definedLabels(text, at - offset));
  const mentions = mentionedLabels(text);
  return defines.length === 0 && mentions.length === 0 ? NO_REFS : { defines, mentions };
}

/**
 * The first and last of `pieces` that define a label or use one some piece
 * defines, or null when no piece defines one.
 */
export function tiedSpan(pieces: readonly PieceRefs[]): { first: number; last: number } | null {
  const labels = new Set(pieces.flatMap((piece) => piece.defines));
  if (labels.size === 0) return null;
  const tied = (piece: PieceRefs) =>
    piece.defines.length > 0 || piece.mentions.some((label) => labels.has(label));
  const first = pieces.findIndex(tied);
  let last = pieces.length - 1;
  while (!tied(pieces[last]!)) last -= 1;
  return { first, last };
}

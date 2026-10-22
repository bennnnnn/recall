/**
 * Where a streaming reply's chunk may end inside a list (`streamBlocks.ts`):
 * between two items of one top-level list, drawn as a list that goes on in
 * the next chunk, only when the cut cannot change how the list is drawn.
 */

/**
 * The top-level list the scan is in. A numbered list's `next` is the number
 * its next item shows (markdown numbers items from the first one, whatever
 * they say). `irregular`: a line markdown may read either way, or numbering
 * that does not run on, so no cut is made in this list.
 */
export type OpenList = { marker: string; next: number | null; irregular: boolean };

/** What the chunk scan knows about the lines before the one it reads. */
export type ListScan = { list: OpenList | null; inBlankRun: boolean };

/**
 * A numbered list's number column is as wide as its largest number. A chunk
 * that ends at item 10 or later already has the width every item up to 99
 * shares, so the items after it cannot widen the column the chunk drew.
 */
const MIN_NUMBERED_CUT = 11;
const MAX_NUMBERED_CUT = 99;

/** An indented line: it belongs to the block above it. */
export const CONTINUATION_LINE_RE = /^(?: {2,}|\t)/;
const BULLET_ITEM_RE = /^([-*+])[ \t]/;
const NUMBERED_ITEM_RE = /^(\d{1,9})([.)])[ \t]/;
const THEMATIC_BREAK_RE = /^(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$/;

/** The top-level list item `line` opens, if any: its marker and number. */
function readListItem(line: string): { marker: string; number: number | null } | null {
  if (THEMATIC_BREAK_RE.test(line)) return null;
  const bullet = BULLET_ITEM_RE.exec(line);
  if (bullet) return { marker: bullet[1]!, number: null };
  const numbered = NUMBERED_ITEM_RE.exec(line);
  if (numbered) return { marker: numbered[2]!, number: Number(numbered[1]) };
  return null;
}

/**
 * Follow the top-level list through a prose line; true when the line is the
 * next item of the open list and a cut before it draws the same list.
 */
export function listItemCut(state: ListScan, line: string): boolean {
  const item = readListItem(line);
  const list = state.list;
  if (item) {
    const sameList =
      list != null && list.marker === item.marker && (list.next === null) === (item.number === null);
    if (!sameList) {
      state.list = {
        marker: item.marker,
        next: item.number === null ? null : item.number + 1,
        irregular: false,
      };
      return false;
    }
    if (item.number === null) return !list.irregular;
    const shown = list.next ?? 0;
    list.next = shown + 1;
    if (item.number !== shown) {
      list.irregular = true;
      return false;
    }
    return !list.irregular && shown >= MIN_NUMBERED_CUT && shown <= MAX_NUMBERED_CUT;
  }
  if (CONTINUATION_LINE_RE.test(line) || !list) return false;
  if (state.inBlankRun) {
    state.list = null;
  } else {
    // A lazy continuation, or a block that ends the list: either way, no cut.
    list.irregular = true;
  }
  return false;
}

/** The text at `at` opens the next item of `list`, as when the chunk before it was cut. */
export function listGoesOn(list: OpenList | null, prepared: string, at: number): boolean {
  if (!list) return false;
  const nl = prepared.indexOf("\n", at);
  const item = readListItem(prepared.slice(at, nl === -1 ? prepared.length : nl));
  if (!item || item.marker !== list.marker) return false;
  return list.next === null ? item.number === null : item.number === list.next;
}

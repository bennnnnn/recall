/**
 * A reply's links, as the phone reads them.
 *
 * The reply's model marks each name it recommends to look up, `[Zuni Café](check "San
 * Francisco")`, and the server alone places it when the reply is saved: its own site from the
 * turn's search results, else Maps for a place, else a search (apps/api
 * `modules/chat/name_links.py`, `reply_links.py`). While the reply streams a mark is drawn as
 * its words, never as a link: which marks become links (a name, not "a taqueria"; not on a
 * heading; the first time only) is the server's rule, and the saved reply's link appears when
 * it settles. docs/fixtures/name_links.json holds what the server writes.
 */

/** The address the reply's model writes for a name to look up (the API's `CHECK_MARKER`). */
const CHECK_MARKER = "check";

/** A name still marked to look up: the reply is streaming, and the server has not placed it. */
export function isNameMark(href: string): boolean {
  const target = href.trim().toLowerCase();
  return target === CHECK_MARKER || target.startsWith(`${CHECK_MARKER}:`) || target.startsWith(`${CHECK_MARKER}%3a`);
}

/** Fix model output where markdown links use $url$ instead of (url).
 * Only fires when the delimited content looks like a URL — otherwise adjacent
 * inline math spans merge: `$x \in [0,2]$ \times $y \in [1,3]$` would turn
 * `[0,2]$ \times $` into `[0,2]( \times )`, leaking the `$` delimiters and
 * painting `0,2` as a blue link. */
export function repairBrokenMarkdownLinks(content: string): string {
  return content.replace(
    /\[([^\]\n]+)\]\$([^$\n]+?)\$/g,
    (full, label: string, url: string) =>
      looksLikeUrl(url) ? `[${label}](${url})` : full,
  );
}

function looksLikeUrl(s: string): boolean {
  const t = s.trim();
  if (!t) return false;
  return /:\/\//.test(t) || /^www\./i.test(t) || /^\.{0,2}\//.test(t);
}

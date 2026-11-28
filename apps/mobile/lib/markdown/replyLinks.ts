/**
 * Where a reply's link opens.
 *
 * The reply's model marks each name it recommends to look up, `[Zuni Café](check "San
 * Francisco")`, and the server places it when the reply is saved: its own site from the
 * turn's search results, else Maps for a place, else a search (apps/api
 * `modules/chat/name_links.py`). While the reply streams the mark is still there, so a tap
 * opens Maps or a search the way the server would without a result to go by;
 * docs/fixtures/name_links.json holds the two to the same addresses. Every other link opens
 * its own address, through the scheme guard (`lib/linkSchemePolicy.ts`).
 */

/** The address the reply's model writes for a name to look up (the API's `CHECK_MARKER`). */
const CHECK_MARKER = "check";
const MAPS_SEARCH = "https://www.google.com/maps/search/?api=1&query=";
const WEB_SEARCH = "https://www.google.com/search?q=";
const EMPHASIS = /[*_`]+/g;
const TITLE_QUOTES = /^["'(\s]+|["')\s]+$/g;
// The typographer's curly quotes, read back as the model wrote them ("Ben & Jerry’s").
const CURLY_SINGLE = /[\u2018\u2019]/g;
const CURLY_DOUBLE = /[\u201C\u201D]/g;

/** Google Maps search link: opens Maps on iOS and Android. */
function googleMapsSearchUrl(query: string): string {
  const q = query.trim();
  return q ? `${MAPS_SEARCH}${encodeURIComponent(q)}` : "";
}

/**
 * The name a link's words say, as the reply wrote it: no emphasis marks, the typographer's
 * curly quotes straight again, one space between words (the API's `name_text`).
 */
function nameText(words: string): string {
  const plain = words.replace(EMPHASIS, "").replace(CURLY_SINGLE, "'").replace(CURLY_DOUBLE, '"');
  return plain.split(/\s+/).filter(Boolean).join(" ");
}

/** A link target as written: markdown-it escapes "check:Zürich" to "check:Z%C3%BCrich". */
function decoded(text: string): string {
  try {
    return decodeURIComponent(text);
  } catch (error) {
    // A stray "%" the model wrote is no escape: the city stays as written.
    if (error instanceof URIError) return text;
    throw error;
  }
}

/** Where a marked name opens with no search result to go by: Maps with its city, else a search. */
export function nameLinkUrl(name: string, city: string): string {
  const text = nameText(name);
  if (!text) return "";
  const place = city.trim();
  return place ? googleMapsSearchUrl(`${text}, ${place}`) : `${WEB_SEARCH}${encodeURIComponent(text)}`;
}

/**
 * The address a tap on a reply link opens: a marked name's Maps or search link, or the
 * link's own address. `title` is the link's title, where a marked place gives its city. A
 * saved reply's names are already placed by the server, so only a reply still streaming
 * (or one the server never finished) reaches the marked branch.
 */
export function replyLinkUrl(href: string, words: string, title = ""): string {
  const target = href.trim();
  const lower = target.toLowerCase();
  if (lower !== CHECK_MARKER && !lower.startsWith(`${CHECK_MARKER}:`)) return target;
  const after = decoded(target.slice(CHECK_MARKER.length).replace(/^:/, ""));
  const city = `${after} ${title}`.replace(TITLE_QUOTES, "").split(/\s+/).filter(Boolean).join(" ");
  return nameLinkUrl(words, city);
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

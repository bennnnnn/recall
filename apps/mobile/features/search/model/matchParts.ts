type MatchPart = { text: string; match: boolean };

/**
 * A result's text cut where the search matched, to highlight it. The server finds the
 * query as one piece in any case, so this marks the same. A title found only by a
 * near spelling holds no exact piece and comes back whole.
 */
export function matchParts(text: string, query: string): MatchPart[] {
  const needle = query.trim().toLowerCase();
  const haystack = text.toLowerCase();
  // Lower case can change a string's length (İ); then its indexes no longer line up.
  if (!needle || haystack.length !== text.length) return [{ text, match: false }];
  const parts: MatchPart[] = [];
  let from = 0;
  for (let at = haystack.indexOf(needle); at !== -1; at = haystack.indexOf(needle, from)) {
    if (at > from) parts.push({ text: text.slice(from, at), match: false });
    parts.push({ text: text.slice(at, at + needle.length), match: true });
    from = at + needle.length;
  }
  if (from < text.length) parts.push({ text: text.slice(from), match: false });
  return parts.length > 0 ? parts : [{ text, match: false }];
}

/**
 * Shared search helpers for the My Job pickers (job titles, skills).
 * Linear scans only — no regex backtracking.
 */

/**
 * Ranked filter: exact-prefix matches first, then word-prefix, then
 * substring. `exclude` (already-picked values) is skipped case-insensitively.
 * No cap unless `limit` is passed — picker sheets are virtualized, so every
 * option stays reachable by scrolling.
 */
export function rankedOptions(
  list: readonly string[],
  query: string,
  exclude: readonly string[] = [],
  limit?: number,
): string[] {
  const cap = limit ?? list.length;
  const q = query.trim().toLowerCase();
  const excluded = new Set(exclude.map((value) => value.toLowerCase()));
  if (!q) {
    return list.filter((item) => !excluded.has(item.toLowerCase())).slice(0, cap);
  }
  const prefix: string[] = [];
  const wordPrefix: string[] = [];
  const substring: string[] = [];
  for (const item of list) {
    const lower = item.toLowerCase();
    if (excluded.has(lower)) continue;
    if (lower.startsWith(q)) {
      prefix.push(item);
      continue;
    }
    const words = lower.split(/[\s/-]+/);
    if (words.some((word) => word.startsWith(q))) {
      wordPrefix.push(item);
      continue;
    }
    if (lower.includes(q)) substring.push(item);
  }
  return [...prefix, ...wordPrefix, ...substring].slice(0, cap);
}

/** Exact (case-insensitive) match against a list → canonical casing. */
export function matchOption(list: readonly string[], text: string): string | null {
  const needle = text.trim().toLowerCase();
  if (!needle) return null;
  for (const item of list) {
    if (item.toLowerCase() === needle) return item;
  }
  return null;
}

const MIN_CUSTOM_OPTION_LENGTH = 3;

/**
 * Guard against junk free-text entries ("bb"). A custom option must be at
 * least 3 characters and contain a letter. List picks bypass this.
 */
export function isValidCustomOption(text: string): boolean {
  const trimmed = text.trim();
  if (trimmed.length < MIN_CUSTOM_OPTION_LENGTH) return false;
  for (const char of trimmed) {
    if (/[a-z]/i.test(char)) return true;
  }
  return false;
}

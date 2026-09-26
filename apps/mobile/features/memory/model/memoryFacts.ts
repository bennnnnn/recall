export const MEMORY_TEXT_MAX_LENGTH = 4000;

/** The server owns the freshness stamp; editing changes the remembered text. */
export function stripMemoryAsOf(text: string): string {
  return text.trim().replace(/^As of \d{4}-\d{2}-\d{2}:\s*/i, "").trim();
}

/** Split memory section text into individual facts (mirrors backend split_memory_facts). */
export function splitMemoryFacts(text: string): string[] {
  const trimmed = text.trim();
  if (!trimmed) return [];
  return trimmed
    .split(/(?<=[.!?])\s+/)
    .map((part) => part.trim())
    .filter(Boolean);
}

/** Join facts for optimistic UI (mirrors backend join_memory_facts / normalize_memory_text). */
export function joinMemoryFacts(facts: string[]): string {
  const parts: string[] = [];
  const seen = new Set<string>();
  for (const raw of facts) {
    const clean = raw.trim().replace(/\s+/g, " ").replace(/\.+$/, "");
    if (!clean) continue;
    const key = clean.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    parts.push(clean);
  }
  let merged = parts.join(". ");
  if (merged && !merged.endsWith(".")) {
    merged += ".";
  }
  return merged;
}

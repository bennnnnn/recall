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

/** Strip a leading `As of YYYY-MM-DD:` stamp (mirrors backend strip_memory_as_of). */
export function stripMemoryAsOf(text: string): string {
  const trimmed = text.trim();
  const prefix = "as of ";
  if (trimmed.toLowerCase().startsWith(prefix) && trimmed.length >= prefix.length + 10) {
    const date = trimmed.slice(prefix.length, prefix.length + 10);
    const year = date.slice(0, 4);
    const month = date.slice(5, 7);
    const day = date.slice(8, 10);
    const sepOk = date[4] === "-" && date[7] === "-";
    const digits =
      [...year, ...month, ...day].every((ch) => ch >= "0" && ch <= "9");
    if (sepOk && digits && trimmed.slice(prefix.length + 10, prefix.length + 12) === ": ") {
      return trimmed.slice(prefix.length + 12).trim();
    }
  }
  return trimmed;
}

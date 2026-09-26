import { MESSAGE_FOLD_MAX_HEIGHT } from "@/lib/markdown/messageFold";

export const MEMORY_TEXT_MAX_LENGTH = 4000;

/** Rough card chrome so a long list can fold without mounting every row. */
const SECTION_HEADER_HEIGHT = 40;
const FACT_LINE_HEIGHT = 24;
const FACT_ROW_CHROME = 16;
const FACT_CHARS_PER_LINE = 40;

function factRowHeight(text: string): number {
  const lines = Math.max(1, Math.ceil(Math.max(text.length, 1) / FACT_CHARS_PER_LINE));
  return FACT_ROW_CHROME + lines * FACT_LINE_HEIGHT;
}

export function memoryBlockHeight(sections: { facts: { text: string }[] }[]): number {
  let height = 0;
  for (const section of sections) {
    height += SECTION_HEADER_HEIGHT;
    for (const fact of section.facts) height += factRowHeight(fact.text);
  }
  return height;
}

/** Rows that fit in the fold. The rest stay unmounted until Show more. */
export function visibleMemorySections<T extends { facts: { text: string }[] }>(
  sections: T[],
  maxHeight = MESSAGE_FOLD_MAX_HEIGHT,
): { sections: T[]; overflows: boolean } {
  if (memoryBlockHeight(sections) <= maxHeight) return { sections, overflows: false };
  let used = 0;
  const visible: T[] = [];
  for (const section of sections) {
    const kept: T["facts"] = [];
    let sectionHeight = SECTION_HEADER_HEIGHT;
    for (const fact of section.facts) {
      const row = factRowHeight(fact.text);
      const alreadyShowing = kept.length > 0 || visible.length > 0;
      if (used + sectionHeight + row > maxHeight && alreadyShowing) {
        if (kept.length > 0) visible.push({ ...section, facts: kept });
        return { sections: visible, overflows: true };
      }
      kept.push(fact);
      sectionHeight += row;
    }
    visible.push(section);
    used += sectionHeight;
  }
  return { sections: visible, overflows: true };
}

export type MemoryPageLabel = { type: string; label: string };

/** One page of memory: a section label, then each fact on its own line. */
export function formatMemoryPage(
  sections: { label: string; facts: string[] }[],
): string {
  return sections
    .filter((section) => section.facts.length > 0)
    .map((section) => [section.label, ...section.facts].join("\n"))
    .join("\n\n");
}

/** Read a page back into per-section fact lines. A label line switches section. */
export function parseMemoryPage(text: string, labels: MemoryPageLabel[]): Map<string, string[]> {
  const typeForLabel = new Map(labels.map((item) => [item.label.trim().toLowerCase(), item.type]));
  const facts = new Map(labels.map((item) => [item.type, [] as string[]]));
  let current = labels[0]?.type ?? "fact";
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line) continue;
    const type = typeForLabel.get(line.toLowerCase());
    if (type) {
      current = type;
      continue;
    }
    facts.get(current)?.push(line);
  }
  return facts;
}

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

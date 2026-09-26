import type { IconName } from "@/ui/icons/names";

/**
 * One icon per lesson-map theme. Shared between `LearningPathList` (the
 * lesson map) and `VocabCard` (the word page) so a chapter's identity reads
 * the same whether you're picking it or studying inside it.
 *
 * Keyed by `domain` (e.g. `PathChapterProgress.domain`), not by chapter
 * title — Spanish still has several chapters per domain (`Family` →
 * `Immediate family`, `Extended family`, …) and they all share one icon.
 * Falls back to a generic book for any future domain not yet listed here.
 */
const DOMAIN_ICONS: Record<string, IconName> = {
  Greetings: "hand",
  "Numbers and time": "clock",
  Family: "users",
  Food: "apple",
  Home: "house",
  Hotel: "bed",
  Travel: "plane",
  "Daily life": "sun",
  Feelings: "smile",
  "Everyday actions": "zap",
  Communication: "messages",
  Thinking: "lightbulb",
  Describing: "palette",
  "Conversation words": "message-quote",
  "Face and eyes": "eye",
  "Body movement": "footprints",
  Hands: "hand",
  "Body reactions": "activity",
  "Eating and drinking": "utensils",
  "Household actions": "droplet",
  "Mouth and body sounds": "megaphone",
  "Casual expressions": "sparkles",
  SAT: "graduation-cap",
};

const DEFAULT_DOMAIN_ICON: IconName = "book";

export function domainIcon(domain: string | null | undefined): IconName {
  if (!domain) return DEFAULT_DOMAIN_ICON;
  return DOMAIN_ICONS[domain.trim()] ?? DEFAULT_DOMAIN_ICON;
}

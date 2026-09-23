import type { IoniconName } from "@/lib/icons";

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
const DOMAIN_ICONS: Record<string, IoniconName> = {
  Greetings: "hand-left-outline",
  "Numbers and time": "time-outline",
  Family: "people-outline",
  Food: "nutrition-outline",
  Home: "home-outline",
  Hotel: "bed-outline",
  Travel: "airplane-outline",
  "Daily life": "sunny-outline",
  Feelings: "happy-outline",
  "Everyday actions": "flash-outline",
  Communication: "chatbubbles-outline",
  Thinking: "bulb-outline",
  Describing: "color-palette-outline",
  "Conversation words": "chatbox-ellipses-outline",
  "Face and eyes": "eye-outline",
  "Body movement": "walk-outline",
  Hands: "hand-right-outline",
  "Body reactions": "pulse-outline",
  "Eating and drinking": "restaurant-outline",
  "Household actions": "water-outline",
  "Mouth and body sounds": "megaphone-outline",
  "Casual expressions": "sparkles-outline",
  SAT: "school-outline",
};

const DEFAULT_DOMAIN_ICON: IoniconName = "book-outline";

export function domainIcon(domain: string | null | undefined): IoniconName {
  if (!domain) return DEFAULT_DOMAIN_ICON;
  return DOMAIN_ICONS[domain.trim()] ?? DEFAULT_DOMAIN_ICON;
}

import type { LanguageLevel } from "@/lib/api";

export const LANGUAGE_LEVELS: LanguageLevel[] = [
  "level1",
  "level2",
  "level3",
  "level4",
  "level5",
  "level6",
];

export function levelLabel(level: LanguageLevel): string {
  const labels: Record<LanguageLevel, string> = {
    level1: "Beginner",
    level2: "Elementary",
    level3: "Intermediate",
    level4: "Upper intermediate",
    level5: "Advanced",
    level6: "Fluent",
  };
  return labels[level];
}

export function partOfSpeechLabel(pos: string | null | undefined): string {
  if (!pos) return "Other";
  return pos.charAt(0).toUpperCase() + pos.slice(1);
}

export function isLanguageProject(kind: string): boolean {
  return kind === "language" || kind === "vocabulary";
}

export function statusLabel(status: string): string {
  if (status === "mastered") return "Mastered";
  if (status === "learning") return "Learning";
  return "New";
}

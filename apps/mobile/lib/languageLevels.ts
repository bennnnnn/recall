import type { LanguageLevel } from "@/lib/api";

export const LANGUAGE_LEVELS: LanguageLevel[] = [
  "level1",
  "level2",
  "level3",
  "level4",
  "level5",
  "level6",
];

const LEVEL_LABEL_KEYS: Record<LanguageLevel, string> = {
  level1: "projects.level.beginner",
  level2: "projects.level.elementary",
  level3: "projects.level.intermediate",
  level4: "projects.level.upper_intermediate",
  level5: "projects.level.advanced",
  level6: "projects.level.fluent",
};

/** English fallback labels (used by non-React callers like prompt builders). */
const LEVEL_LABELS_EN: Record<LanguageLevel, string> = {
  level1: "Beginner",
  level2: "Elementary",
  level3: "Intermediate",
  level4: "Upper intermediate",
  level5: "Advanced",
  level6: "Fluent",
};

/** Return the English label for a level (non-React callers, prompt builders). */
export function levelLabel(level: LanguageLevel): string {
  return LEVEL_LABELS_EN[level];
}

/** Return the i18n'd label for a level (React components). */
export function levelLabelT(
  level: LanguageLevel,
  t: (key: string) => string,
): string {
  return t(LEVEL_LABEL_KEYS[level]);
}

export function levelPickerOptions(
  t?: (key: string) => string,
): { key: LanguageLevel; label: string }[] {
  return LANGUAGE_LEVELS.map((level) => ({
    key: level,
    label: t ? t(LEVEL_LABEL_KEYS[level]) : LEVEL_LABELS_EN[level],
  }));
}

export function isLanguageProject(kind: string): boolean {
  return kind === "language" || kind === "vocabulary";
}

const STATUS_LABEL_KEYS: Record<string, string> = {
  mastered: "projects.status_mastered",
  learning: "projects.status_learning",
  new: "projects.status_new",
};

const STATUS_LABELS_EN: Record<string, string> = {
  mastered: "Mastered",
  learning: "Learning",
  new: "New",
};

/** Return the English label for a status (non-React callers). */
export function statusLabel(status: string): string {
  return STATUS_LABELS_EN[status] ?? STATUS_LABELS_EN.new;
}

/** Return the i18n'd label for a status (React components). */
export function statusLabelT(
  status: string,
  t: (key: string) => string,
): string {
  return t(STATUS_LABEL_KEYS[status] ?? STATUS_LABEL_KEYS.new);
}

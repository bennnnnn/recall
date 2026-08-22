import type { ProjectKind } from "@/lib/api";
import { languageLabel } from "@/lib/i18n/languages";

/** User-facing title for vocabulary learning screens (list + detail). */
export function learningProjectTitle(
  kind: ProjectKind,
  t: (key: string) => string,
  fallbackTitle = "",
  targetLanguage?: string | null,
): string {
  if (kind === "language" || kind === "vocabulary") {
    return languageLabel(targetLanguage) || fallbackTitle || t("projects.kind.language");
  }
  return fallbackTitle || t("projects.detail");
}

export type ProjectStatLabels = {
  learned: string;
  learnedToday: string;
  new: string;
  thisWeek: string;
  due: string;
};

export function projectStatsLabels(
  _kind: ProjectKind,
  t: (key: string) => string,
): ProjectStatLabels {
  return {
    learned: t("projects.stats.learned"),
    learnedToday: t("projects.stats.mastered_today"),
    new: t("projects.stats.new"),
    thisWeek: t("projects.stats.this_week"),
    due: t("projects.stats.due"),
  };
}

/** Map backend default list buckets to kind-appropriate section titles. */
export function formatProjectListTitle(
  listTitle: string,
  _kind: ProjectKind,
  t: (key: string) => string,
): string {
  const normalized = listTitle.trim().toLowerCase();
  if (normalized === "general") {
    return t("projects.list.general");
  }
  return listTitle;
}

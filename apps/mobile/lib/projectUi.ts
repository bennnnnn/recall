import type { ProjectKind } from "@/lib/api";

export function isConceptProject(_kind: ProjectKind): boolean {
  // Concept/math workspaces are not a product surface — only language + trivia.
  return false;
}

export function isTriviaProject(kind: ProjectKind): boolean {
  return kind === "trivia";
}

/** User-facing title for vocabulary / trivia learning screens (list + detail). */
export function learningProjectTitle(
  kind: ProjectKind,
  t: (key: string) => string,
  fallbackTitle = "",
): string {
  if (kind === "language" || kind === "vocabulary") {
    return t("projects.list.english_title");
  }
  if (kind === "trivia") {
    return t("projects.trivia.title");
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
  kind: ProjectKind,
  t: (key: string) => string,
): ProjectStatLabels {
  if (kind === "language" || kind === "vocabulary") {
    return {
      learned: t("projects.stats.learned"),
      learnedToday: t("projects.stats.mastered_today"),
      new: t("projects.stats.new"),
      thisWeek: t("projects.stats.this_week"),
      due: t("projects.stats.due"),
    };
  }
  return {
    learned: t("projects.stats.correct_total"),
    learnedToday: t("projects.stats.correct_today"),
    new: t("projects.stats.facts_new"),
    thisWeek: t("projects.stats.this_week"),
    due: t("projects.stats.facts_due"),
  };
}

/** Map backend default list buckets to kind-appropriate section titles. */
export function formatProjectListTitle(
  listTitle: string,
  kind: ProjectKind,
  t: (key: string) => string,
): string {
  const normalized = listTitle.trim().toLowerCase();
  if (normalized === "general") {
    return t("projects.list.general");
  }
  return listTitle;
}

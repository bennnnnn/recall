import type { ProjectKind } from "@/lib/api";

export function isConceptProject(kind: ProjectKind): boolean {
  return kind === "math" || kind === "general" || kind === "learning";
}

export function isTriviaProject(kind: ProjectKind): boolean {
  return kind === "trivia";
}

export type ProjectStatLabels = {
  learned: string;
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
      new: t("projects.stats.new"),
      thisWeek: t("projects.stats.this_week"),
      due: t("projects.stats.due"),
    };
  }
  if (kind === "trivia") {
    return {
      learned: t("projects.stats.correct_total"),
      new: t("projects.stats.facts_new"),
      thisWeek: t("projects.stats.this_week"),
      due: t("projects.stats.facts_due"),
    };
  }
  if (kind === "math") {
    return {
      learned: t("projects.stats.concepts_mastered"),
      new: t("projects.stats.concepts_new"),
      thisWeek: t("projects.stats.this_week"),
      due: t("projects.stats.concepts_due"),
    };
  }
  return {
    learned: t("projects.stats.items_mastered"),
    new: t("projects.stats.items_new"),
    thisWeek: t("projects.stats.this_week"),
    due: t("projects.stats.items_due"),
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
    if (kind === "math") return t("projects.list.topics");
    return t("projects.list.general");
  }
  return listTitle;
}

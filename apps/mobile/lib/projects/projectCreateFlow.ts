import type { LanguageLevel, Project, ProjectKind } from "@/lib/api";
import { LEARNING_LANGUAGES, languageLabel } from "@/lib/i18n/languages";
import { findLanguageProject } from "@/lib/projects/languageProject";

export type CreateStep = "language" | "daily";

/** API still requires a class level; unused for vocab (full catalog for everyone). */
export const CREATE_DEFAULT_LEVEL: LanguageLevel = "level1";

export function createStepsForKind(kind: ProjectKind | null): CreateStep[] {
  if (kind === "language" || kind === "vocabulary") return ["language", "daily"];
  return ["language"];
}

export function createStepProgress(
  step: CreateStep,
  kind: ProjectKind | null,
): { current: number; total: number } {
  const steps = createStepsForKind(kind ?? "language");
  const index = steps.indexOf(step);
  return { current: Math.max(index + 1, 1), total: steps.length };
}

export function languageClassTitle(targetLanguage = "en"): string {
  return languageLabel(targetLanguage);
}

export function fallbackProjectTitle(
  kind: ProjectKind,
  t: (key: string) => string,
): string {
  if (kind === "language" || kind === "vocabulary") {
    return languageClassTitle();
  }
  return t("projects.kind.language");
}

export function resolveProjectTitle(
  titleInput: string,
  kind: ProjectKind,
  t: (key: string) => string,
): string {
  const title = titleInput.trim();
  if (title.length > 0) {
    return title.length <= 80 ? title : `${title.slice(0, 77)}…`;
  }
  return fallbackProjectTitle(kind, t);
}

/** Omit description when empty or identical to title (avoids duplicate subtitle on detail). */
export function resolveProjectDescription(titleInput: string, goalInput: string): string {
  const title = titleInput.trim();
  const goal = goalInput.trim();
  if (!goal) return "";
  if (title && goal === title) return "";
  return goal;
}

/** True until every catalog language class exists. */
export function canAddLearningProject(projects: Project[]): boolean {
  const active = projects.filter((project) => !project.archived);
  return LEARNING_LANGUAGES.some((lang) => findLanguageProject(active, lang.code) == null);
}

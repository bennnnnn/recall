import type { Learning, LearningKind } from "@/lib/api";
import { LEARNING_LANGUAGES, languageLabel } from "@/lib/i18n/languages";
import { isLanguageProject } from "@/lib/languageLevels";
import { findLanguageProject } from "@/lib/projects/languageProject";

export type CreateStep = "language" | "daily";

export function createStepsForKind(kind: LearningKind | string | null): CreateStep[] {
  if (isLanguageProject(kind ?? "language")) return ["language", "daily"];
  return ["language"];
}

export function createStepProgress(
  step: CreateStep,
  kind: LearningKind | null,
): { current: number; total: number } {
  const steps = createStepsForKind(kind ?? "language");
  const index = steps.indexOf(step);
  return { current: Math.max(index + 1, 1), total: steps.length };
}

export function languageClassTitle(targetLanguage = "en"): string {
  return languageLabel(targetLanguage);
}

export function fallbackProjectTitle(
  kind: LearningKind,
  t: (key: string) => string,
): string {
  if (isLanguageProject(kind)) {
    return languageClassTitle();
  }
  return t("projects.kind.language");
}

export function resolveProjectTitle(
  titleInput: string,
  kind: LearningKind,
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
export function canAddLearningProject(projects: Learning[]): boolean {
  const active = projects.filter((project) => !project.archived);
  return LEARNING_LANGUAGES.some((lang) => findLanguageProject(active, lang.code) == null);
}

import type { LanguageLevel, Project, ProjectKind } from "@/lib/api";
import { LEARNING_LANGUAGES, languageLabel } from "@/lib/i18n/languages";
import { levelLabel } from "@/lib/languageLevels";
import { findLanguageProject } from "@/lib/projects/languageProject";

export type CreateStep = "language" | "level" | "daily";

export function createStepsForKind(kind: ProjectKind | null): CreateStep[] {
  if (kind === "language" || kind === "vocabulary") return ["language", "level", "daily"];
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

export function goalStepHint(
  kind: ProjectKind,
  level: LanguageLevel,
  t: (key: string) => string,
  targetLanguage = "en",
): string {
  if (kind === "language" || kind === "vocabulary") {
    return `${languageLabel(targetLanguage)} · ${levelLabel(level)}`;
  }
  return t("projects.kind.language");
}

export function languageProjectTitle(level: LanguageLevel, targetLanguage = "en"): string {
  return `${languageLabel(targetLanguage)} · ${levelLabel(level)}`;
}

export function fallbackProjectTitle(
  kind: ProjectKind,
  level: LanguageLevel,
  t: (key: string) => string,
): string {
  if (kind === "language" || kind === "vocabulary") {
    return languageProjectTitle(level);
  }
  return t("projects.kind.language");
}

export function resolveProjectTitle(
  titleInput: string,
  kind: ProjectKind,
  level: LanguageLevel,
  t: (key: string) => string,
): string {
  const title = titleInput.trim();
  if (title.length > 0) {
    return title.length <= 80 ? title : `${title.slice(0, 77)}…`;
  }
  return fallbackProjectTitle(kind, level, t);
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

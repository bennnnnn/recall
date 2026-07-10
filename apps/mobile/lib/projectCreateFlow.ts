import type { LanguageLevel, Project, ProjectKind } from "@/lib/api";
import { levelLabel } from "@/lib/languageLevels";
import { findLanguageProject } from "@/lib/languageProject";
import { findTriviaProject } from "@/lib/triviaProject";

export type CreateStep = "subject" | "level" | "daily" | "topics" | "trivia_level";

export function createStepsForKind(kind: ProjectKind | null): CreateStep[] {
  if (kind === "language") return ["subject", "level", "daily"];
  if (kind === "trivia") return ["subject", "topics", "daily"];
  return ["subject"];
}

export function createStepProgress(
  step: CreateStep,
  kind: ProjectKind | null,
): { current: number; total: number } {
  if (step === "subject") {
    return { current: 1, total: kind ? createStepsForKind(kind).length : 2 };
  }
  if (!kind) return { current: 1, total: 1 };
  const steps = createStepsForKind(kind);
  const index = steps.indexOf(step);
  return { current: index + 1, total: steps.length };
}

export function goalStepHint(
  kind: ProjectKind,
  level: LanguageLevel,
  t: (key: string) => string,
): string {
  if (kind === "language") {
    return `${t("projects.kind.language")} · ${levelLabel(level)}`;
  }
  return t(`projects.kind.${kind === "vocabulary" ? "language" : kind}`);
}

export function englishProjectTitle(
  level: LanguageLevel,
  t: (key: string) => string,
): string {
  return `${t("projects.kind.language")} · ${levelLabel(level)}`;
}

export function triviaProjectTitle(t: (key: string) => string): string {
  return t("projects.trivia.title");
}

export function fallbackProjectTitle(
  kind: ProjectKind,
  level: LanguageLevel,
  t: (key: string) => string,
): string {
  if (kind === "language") {
    return englishProjectTitle(level, t);
  }
  if (kind === "trivia") {
    return triviaProjectTitle(t);
  }
  return t(`projects.kind.${kind}`);
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

/** v1 learning is capped at English vocabulary + general knowledge. */
export function canAddLearningProject(projects: Project[]): boolean {
  const active = projects.filter((project) => !project.archived);
  const hasLanguage = findLanguageProject(active, "en") != null;
  const hasTrivia = findTriviaProject(active) != null;
  return !(hasLanguage && hasTrivia);
}

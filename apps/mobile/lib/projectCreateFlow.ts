import type { LanguageLevel, ProjectKind } from "@/lib/api";
import type { ProgrammingLanguageId } from "@/lib/programmingLanguages";
import { levelLabel } from "@/lib/languageLevels";
import { programmingLanguageLabel } from "@/lib/programmingLanguages";

export type CreateStep = "subject" | "level" | "daily" | "stack" | "topics";

export function createStepsForKind(kind: ProjectKind | null): CreateStep[] {
  if (kind === "language") return ["subject", "level", "daily"];
  if (kind === "trivia") return ["subject", "topics", "daily"];
  if (kind === "programming") return ["subject", "stack"];
  return ["subject"];
}

export function createStepProgress(
  step: CreateStep,
  kind: ProjectKind | null,
): { current: number; total: number } {
  if (step === "subject") {
    return { current: 1, total: kind ? createStepsForKind(kind).length : 3 };
  }
  if (!kind) return { current: 1, total: 1 };
  const steps = createStepsForKind(kind);
  const index = steps.indexOf(step);
  return { current: index + 1, total: steps.length };
}

export function goalStepHint(
  kind: ProjectKind,
  level: LanguageLevel,
  programmingLanguage: ProgrammingLanguageId | null,
  t: (key: string) => string,
): string {
  if (kind === "language") {
    return `${t("projects.kind.language")} · ${levelLabel(level)}`;
  }
  if (kind === "programming" && programmingLanguage) {
    return `${programmingLanguageLabel(programmingLanguage)} · ${t("projects.kind.programming")}`;
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

export function programmingProjectTitle(
  programmingLanguage: ProgrammingLanguageId,
  t: (key: string) => string,
): string {
  return `${programmingLanguageLabel(programmingLanguage)} · ${t("projects.kind.programming")}`;
}

export function fallbackProjectTitle(
  kind: ProjectKind,
  level: LanguageLevel,
  programmingLanguage: ProgrammingLanguageId | null,
  t: (key: string) => string,
): string {
  if (kind === "language") {
    return englishProjectTitle(level, t);
  }
  if (kind === "programming" && programmingLanguage) {
    return programmingProjectTitle(programmingLanguage, t);
  }
  return t(`projects.kind.${kind}`);
}

export function resolveProjectTitle(
  titleInput: string,
  kind: ProjectKind,
  level: LanguageLevel,
  programmingLanguage: ProgrammingLanguageId | null,
  t: (key: string) => string,
): string {
  const title = titleInput.trim();
  if (title.length > 0) {
    return title.length <= 80 ? title : `${title.slice(0, 77)}…`;
  }
  return fallbackProjectTitle(kind, level, programmingLanguage, t);
}

/** Omit description when empty or identical to title (avoids duplicate subtitle on detail). */
export function resolveProjectDescription(titleInput: string, goalInput: string): string {
  const title = titleInput.trim();
  const goal = goalInput.trim();
  if (!goal) return "";
  if (title && goal === title) return "";
  return goal;
}

export function titlePlaceholderKey(kind: ProjectKind): string {
  if (kind === "math") return "projects.title_placeholder_math";
  return "projects.title_placeholder_programming";
}

export function goalPlaceholderKey(kind: ProjectKind): string {
  if (kind === "math") return "projects.goal_placeholder_math";
  return "projects.goal_placeholder_programming";
}

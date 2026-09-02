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

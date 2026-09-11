import { isLanguageProject } from "@/lib/languageLevels";
import { languageLabel } from "@/lib/i18n/languages";

/** User-facing title for vocabulary learning screens (list + detail). */
export function learningProjectTitle(
  kind: string,
  t: (key: string) => string,
  fallbackTitle = "",
  targetLanguage?: string | null,
): string {
  if (isLanguageProject(kind)) {
    return languageLabel(targetLanguage) || fallbackTitle || t("projects.kind.language");
  }
  return fallbackTitle || t("projects.detail");
}

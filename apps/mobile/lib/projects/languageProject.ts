import type { Learning } from "@/lib/api";
import { isLanguageProject } from "@/lib/languageLevels";

/** One vocabulary workspace per target language (e.g. a single English project). */
export function findLanguageProject(
  projects: Learning[],
  targetLanguage = "en",
): Learning | undefined {
  const lang = targetLanguage.trim().toLowerCase();
  return projects.find(
    (p) => isLanguageProject(p.kind) && p.target_language.trim().toLowerCase() === lang,
  );
}

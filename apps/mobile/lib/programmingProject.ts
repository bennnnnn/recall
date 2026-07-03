import type { Project } from "@/lib/api";
import { isProgrammingStack } from "@/lib/programmingLanguages";

/** One programming workspace per stack (python, javascript, …). */
export function findProgrammingProject(
  projects: Project[],
  targetLanguage: string,
): Project | undefined {
  const lang = targetLanguage.trim().toLowerCase();
  return projects.find(
    (p) => p.kind === "programming" && p.target_language.trim().toLowerCase() === lang,
  );
}

export function findAnyProgrammingProject(projects: Project[]): Project | undefined {
  return projects.find((p) => p.kind === "programming" && isProgrammingStack(p.target_language));
}

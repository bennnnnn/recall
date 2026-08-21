import type { Project } from "@/lib/api";

export function findTriviaProject(projects: Project[]): Project | undefined {
  return projects.find((project) => project.kind === "trivia");
}

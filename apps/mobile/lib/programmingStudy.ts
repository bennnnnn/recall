import type { ProjectDetail, ProjectListGroup } from "@/lib/api";
import { buildProjectAskPrompt } from "@/lib/projectChat";

function itemMastered(item: { status: string; mastered: boolean }): boolean {
  return item.status === "mastered" || item.mastered;
}

/** First chapter that still has uncovered sub-topics. */
export function suggestProgrammingTopic(lists: ProjectListGroup[]): string | null {
  for (const group of lists) {
    const hasPending = group.items.some((item) => !itemMastered(item));
    if (hasPending) return group.list_title;
  }
  return null;
}

export function buildProgrammingStudyPrompt(project: ProjectDetail, chapter: string): string {
  const trimmed = chapter.trim();
  if (!trimmed) return "";
  const lists = project.lists ?? [];
  const group = lists.find((g) => g.list_title === trimmed);
  const pending = (group?.items ?? []).filter((item) => !itemMastered(item));
  const topics = pending.map((item) => item.content);
  const stack = project.target_language;
  const base = buildProjectAskPrompt(project);
  return (
    `${base}\n\n` +
    `Help me study the **${trimmed}** chapter in my ${stack} programming journey. ` +
    `Cover these sub-topics I have not finished yet: ${topics.join(", ") || trimmed}. ` +
    `Teach one sub-topic at a time with ${stack} examples, check my understanding, ` +
    `then mark each sub-topic mastered when I demonstrate it.`
  );
}

export function buildProgrammingNextUpPrompt(project: ProjectDetail): string {
  const chapter = suggestProgrammingTopic((project.lists ?? []) as ProjectListGroup[]);
  if (!chapter) return buildProjectAskPrompt(project);
  return buildProgrammingStudyPrompt(project, chapter);
}

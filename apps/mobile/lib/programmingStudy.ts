import type { ProjectItem, ProjectListGroup, ProjectDetail } from "@/lib/api";
import { buildProjectAskPrompt } from "@/lib/projectChat";

function itemMastered(item: ProjectItem): boolean {
  return item.status === "mastered" || item.mastered;
}

function itemLearning(item: ProjectItem): boolean {
  return item.status === "learning";
}

function topicStats(items: ProjectItem[]) {
  const total = items.length;
  const mastered = items.filter(itemMastered).length;
  const learning = items.filter(itemLearning).length;
  return { total, mastered, learning, pending: total - mastered };
}

export function suggestProgrammingTopic(lists: ProjectListGroup[]): string | null {
  let best: { title: string; score: number } | null = null;
  for (const group of lists) {
    const { total, mastered, learning, pending } = topicStats(group.items);
    if (total === 0 || pending === 0) continue;
    const score = pending + learning * 0.25;
    if (!best || score > best.score) {
      best = { title: group.list_title, score };
    }
  }
  return best?.title ?? null;
}

export function buildProgrammingStudyPrompt(
  project: ProjectDetail,
  topic: string,
): string {
  const lists = project.lists ?? [];
  const group = lists.find((g) => g.list_title === topic);
  const pending = (group?.items ?? []).filter(
    (item) => item.status !== "mastered" && !item.mastered,
  );
  const concepts = pending.map((item) => item.content).slice(0, 5);
  const stack = project.target_language;
  const base = buildProjectAskPrompt(project);
  return (
    `${base}\n\n` +
    `Help me study the **${topic}** topic in my ${stack} learning journey. ` +
    `Focus on these concepts I have not mastered yet: ${concepts.join(", ") || topic}. ` +
    `Explain clearly, give a short example, then ask me a quick check question. ` +
    `When I demonstrate understanding, mark the concept as learned.`
  );
}

export function buildProgrammingNextUpPrompt(project: ProjectDetail): string {
  const topic =
    suggestProgrammingTopic((project.lists ?? []) as ProjectListGroup[]) ??
    "Variables";
  return buildProgrammingStudyPrompt(project, topic);
}

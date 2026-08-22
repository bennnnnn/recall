import type { PathChapterProgress, ProjectDetail, ProjectItem } from "@/lib/api";

import { chapterKey } from "@/lib/projects/chapterAccess";

export function chapterItems(project: ProjectDetail, title: string): ProjectItem[] {
  const key = chapterKey(title);
  const group = project.lists.find((entry) => chapterKey(entry.list_title) === key);
  return group?.items ?? [];
}

export function chapterQueue(items: ProjectItem[]): ProjectItem[] {
  const pending = items.filter((item) => item.status !== "mastered" && !item.mastered);
  return pending.length > 0 ? pending : items;
}

export function resolveLessonChapter(
  project: ProjectDetail,
  requested?: string | null,
): string | null {
  const wanted = requested?.trim();
  if (wanted) return wanted;
  if (project.up_next?.trim()) return project.up_next.trim();
  return project.path_progress?.[0]?.title ?? project.lists[0]?.list_title ?? null;
}

export function chapterProgress(
  project: ProjectDetail,
  title: string,
): PathChapterProgress | null {
  const key = chapterKey(title);
  return project.path_progress?.find((entry) => chapterKey(entry.title) === key) ?? null;
}

export function itemToCard(item: ProjectItem): {
  word: string;
  definition: string;
  exampleSentence?: string;
} {
  const example = item.example_sentence?.trim() || item.note?.trim();
  return {
    word: item.content,
    definition: item.definition?.trim() || item.content,
    ...(example ? { exampleSentence: example } : {}),
  };
}

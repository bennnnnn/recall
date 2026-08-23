import type { PathChapterProgress, ProjectDetail, ProjectItem } from "@/lib/api";

import { chapterKey } from "@/lib/projects/chapterAccess";

export function chapterItems(project: ProjectDetail, title: string): ProjectItem[] {
  const key = chapterKey(title);
  const group = project.lists.find((entry) => chapterKey(entry.list_title) === key);
  return group?.items ?? [];
}

export function isItemMastered(item: Pick<ProjectItem, "status" | "mastered">): boolean {
  return item.status === "mastered" || item.mastered;
}

export function chapterIsComplete(items: Pick<ProjectItem, "status" | "mastered">[]): boolean {
  return items.length > 0 && items.every(isItemMastered);
}

export function applyItemOutcome(
  items: ProjectItem[],
  itemId: string,
  failed: boolean,
): ProjectItem[] {
  return items.map((item) =>
    item.id === itemId
      ? { ...item, status: failed ? "learning" : "mastered", mastered: !failed }
      : item,
  );
}

/** Overlay in-session save results onto chapter items (`failed` = keep learning). */
export function overlayItemOutcomes(
  items: ProjectItem[],
  outcomes: Record<string, boolean>,
): ProjectItem[] {
  let next = items;
  for (const [itemId, failed] of Object.entries(outcomes)) {
    next = applyItemOutcome(next, itemId, failed);
  }
  return next;
}

/** Pending words only, capped so one sitting matches the daily goal. */
export function chapterQueue(items: ProjectItem[], limit?: number): ProjectItem[] {
  const pending = items.filter((item) => !isItemMastered(item));
  const queue = pending.length > 0 ? pending : items;
  if (limit != null && limit > 0) return queue.slice(0, limit);
  return queue;
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

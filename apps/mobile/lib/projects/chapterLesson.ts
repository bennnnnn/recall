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

/** Pending words: "Not yet" (`learning`) first, then new, capped to the daily goal. */
export function chapterQueue(items: ProjectItem[], limit?: number): ProjectItem[] {
  const pending = items.filter((item) => !isItemMastered(item));
  const learning = pending.filter((item) => item.status === "learning");
  const fresh = pending.filter((item) => item.status !== "learning");
  const queue = pending.length > 0 ? [...learning, ...fresh] : items;
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

export type LessonVocabCard = {
  word: string;
  definition: string;
  exampleSentence?: string;
  ipa?: string;
  partOfSpeech?: string;
  simpleGloss?: string;
};

export function itemToCard(item: ProjectItem): LessonVocabCard {
  const example = item.example_sentence?.trim() || item.note?.trim();
  const ipa = item.ipa?.trim();
  const partOfSpeech = item.part_of_speech?.trim();
  const simpleGloss = item.simple_gloss?.trim();
  return {
    word: item.content,
    definition: item.definition?.trim() || item.content,
    ...(example ? { exampleSentence: example } : {}),
    ...(ipa ? { ipa } : {}),
    ...(partOfSpeech ? { partOfSpeech } : {}),
    ...(simpleGloss ? { simpleGloss } : {}),
  };
}

/** Split `sentence` so the lemma can be bolded. Linear scan — no regex. */
export function highlightLemmaParts(
  sentence: string,
  lemma: string,
): { text: string; match: boolean }[] {
  const target = lemma.trim();
  if (!sentence) return [];
  if (!target) return [{ text: sentence, match: false }];
  const haystack = sentence.toLowerCase();
  const needle = target.toLowerCase();
  const parts: { text: string; match: boolean }[] = [];
  let from = 0;
  while (from < sentence.length) {
    const at = haystack.indexOf(needle, from);
    if (at === -1) {
      parts.push({ text: sentence.slice(from), match: false });
      break;
    }
    if (at > from) parts.push({ text: sentence.slice(from, at), match: false });
    parts.push({ text: sentence.slice(at, at + target.length), match: true });
    from = at + target.length;
  }
  return parts.filter((part) => part.text.length > 0);
}

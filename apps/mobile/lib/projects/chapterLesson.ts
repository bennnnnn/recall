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

export function applyItemMastered(items: ProjectItem[], itemId: string): ProjectItem[] {
  return items.map((item) =>
    item.id === itemId ? { ...item, status: "mastered", mastered: true } : item,
  );
}

/** Overlay in-session Next saves onto chapter items. */
export function overlayMasteredItems(
  items: ProjectItem[],
  masteredIds: Record<string, true>,
): ProjectItem[] {
  let next = items;
  for (const itemId of Object.keys(masteredIds)) {
    next = applyItemMastered(next, itemId);
  }
  return next;
}

/** Play-screen header: words already done in this group vs the group's size.
 *  Learning: `current` is the next slot (mastered + 1); the bar is mastered/total.
 *  Review of a finished group: `current` is this word's place in the group. */
export function groupLessonProgress(
  items: Pick<ProjectItem, "id" | "status" | "mastered">[],
  currentItemId: string | null,
): { current: number; total: number; fill: number } {
  const total = items.length;
  if (total === 0) return { current: 0, total: 0, fill: 0 };
  const mastered = items.filter(isItemMastered).length;
  if (chapterIsComplete(items)) {
    const at = currentItemId
      ? items.findIndex((item) => item.id === currentItemId)
      : -1;
    const current = at >= 0 ? at + 1 : total;
    return { current, total, fill: current / total };
  }
  const onPending =
    currentItemId != null &&
    items.some((item) => item.id === currentItemId && !isItemMastered(item));
  return {
    current: Math.min(total, mastered + (onPending ? 1 : 0)),
    total,
    fill: mastered / total,
  };
}

/** Pending words, capped to the daily goal so a sitting is today's batch.
 *  A finished chapter returns every word for review and ignores the daily cap. */
export function chapterQueue(items: ProjectItem[], limit?: number): ProjectItem[] {
  const pending = items.filter((item) => !isItemMastered(item));
  if (pending.length === 0) return items;
  const learning = pending.filter((item) => item.status === "learning");
  const fresh = pending.filter((item) => item.status !== "learning");
  const queue = [...learning, ...fresh];
  if (limit != null && limit > 0) return queue.slice(0, limit);
  return queue;
}

export function isChapterReview(items: Pick<ProjectItem, "status" | "mastered">[]): boolean {
  return chapterIsComplete(items);
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

/** Gloss shown on the teaching card and as the meaning-quiz answer. */
export function cardMeaning(card: LessonVocabCard): string {
  return card.simpleGloss?.trim() || card.definition.trim() || card.word.trim();
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

/** Split stored examples (newline-separated, max two) for the word page. */
export function exampleSentences(raw?: string | null): string[] {
  if (!raw) return [];
  const out: string[] = [];
  let rest = raw;
  while (rest.length > 0 && out.length < 2) {
    const at = rest.indexOf("\n");
    const chunk = (at === -1 ? rest : rest.slice(0, at)).trim();
    if (chunk) out.push(chunk);
    rest = at === -1 ? "" : rest.slice(at + 1);
  }
  return out;
}

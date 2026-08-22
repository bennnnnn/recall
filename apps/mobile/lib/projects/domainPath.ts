import type { PathChapterProgress } from "@/lib/api";
import { chapterAccess, chapterKey, type ChapterAccess } from "@/lib/projects/chapterAccess";

export type DomainProgress = {
  title: string;
  mastered: number;
  total: number;
  complete: boolean;
  chapters: PathChapterProgress[];
};

export function groupPathByDomain(path: PathChapterProgress[]): DomainProgress[] {
  const order: string[] = [];
  const grouped = new Map<string, PathChapterProgress[]>();
  for (const chapter of path) {
    const domain = chapter.domain?.trim() || chapter.title;
    if (!grouped.has(domain)) {
      order.push(domain);
      grouped.set(domain, []);
    }
    grouped.get(domain)?.push(chapter);
  }
  return order.map((title) => {
    const chapters = grouped.get(title) ?? [];
    return {
      title,
      mastered: chapters.reduce((sum, chapter) => sum + chapter.mastered, 0),
      total: chapters.reduce((sum, chapter) => sum + chapter.total, 0),
      complete: chapters.length > 0 && chapters.every((chapter) => chapter.complete),
      chapters,
    };
  });
}

export function domainForChapter(
  path: PathChapterProgress[],
  chapterTitle: string | null | undefined,
): string | null {
  if (!chapterTitle?.trim()) return null;
  const key = chapterKey(chapterTitle);
  const match = path.find((chapter) => chapterKey(chapter.title) === key);
  const domain = match?.domain?.trim() || match?.title;
  return domain || null;
}

export function domainAccess(
  domains: DomainProgress[],
  title: string,
  upNext?: string | null,
): ChapterAccess {
  const index = domains.findIndex((domain) => chapterKey(domain.title) === chapterKey(title));
  if (index < 0) return "locked";
  const domain = domains[index];
  if (domain.complete) return "done";
  if (domains.slice(0, index).some((entry) => !entry.complete)) return "locked";
  if (upNext && domain.chapters.some((chapter) => chapterKey(chapter.title) === chapterKey(upNext))) {
    return "current";
  }
  const firstOpen = domains.find((entry) => !entry.complete);
  return firstOpen && chapterKey(firstOpen.title) === chapterKey(title) ? "current" : "locked";
}

export function branchAccess(
  chapter: PathChapterProgress,
  upNext: string | null | undefined,
  domainLocked: boolean,
): ChapterAccess {
  if (domainLocked) return "locked";
  return chapterAccess(chapter, upNext);
}


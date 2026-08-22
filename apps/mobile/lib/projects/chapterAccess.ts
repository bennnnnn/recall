import type { PathChapterProgress } from "@/lib/api";

export type ChapterAccess = "done" | "current" | "locked";

export function chapterKey(title: string): string {
  return title.trim().toLowerCase();
}

export function chapterAccess(
  chapter: PathChapterProgress,
  upNext: string | null | undefined,
): ChapterAccess {
  if (chapter.complete) return "done";
  if (upNext && chapterKey(chapter.title) === chapterKey(upNext)) return "current";
  return "locked";
}

export function lessonMapPath(projectId: string): `/projects/${string}/lesson` {
  return `/projects/${projectId}/lesson`;
}

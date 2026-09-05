/** Queued lesson opener — avoids long prompts in expo-router params. */
import { getSessionGeneration } from "@/lib/auth";
import type { QuizVariant } from "@/lib/quizVariant";

export type QueuedLessonLaunch = {
  projectId: string;
  chapter?: string;
  prompt?: string;
  quizLanguage?: string;
  quizVariant?: QuizVariant;
};

let queued: QueuedLessonLaunch | null = null;
let session = -1;

export function peekQueuedLessonLaunch(projectId?: string): QueuedLessonLaunch | null {
  if (session !== getSessionGeneration()) {
    queued = null;
    return null;
  }
  return queued && (!projectId || queued.projectId === projectId) ? queued : null;
}

export function queueLessonLaunch(launch: QueuedLessonLaunch): boolean {
  const projectId = launch.projectId.trim();
  if (!projectId) return false;
  const prompt = launch.prompt?.trim();
  const chapter = launch.chapter?.trim();
  session = getSessionGeneration();
  queued = {
    projectId,
    ...(chapter ? { chapter } : {}),
    ...(prompt ? { prompt } : {}),
    ...(launch.quizLanguage ? { quizLanguage: launch.quizLanguage } : {}),
    ...(launch.quizVariant ? { quizVariant: launch.quizVariant } : {}),
  };
  return true;
}

export function takeQueuedLessonLaunch(): QueuedLessonLaunch | null {
  if (!peekQueuedLessonLaunch()) return null;
  const next = queued;
  queued = null;
  return next;
}

export function lessonPath(projectId: string): `/projects/${string}/lesson/play` {
  return `/projects/${projectId}/lesson/play`;
}

export function openLearningLesson(
  router: { push: (href: `/projects/${string}/lesson/play`) => void },
  launch: QueuedLessonLaunch,
): boolean {
  if (!queueLessonLaunch(launch)) return false;
  router.push(lessonPath(launch.projectId));
  return true;
}

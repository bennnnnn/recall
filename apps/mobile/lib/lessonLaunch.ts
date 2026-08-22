/** Queued lesson opener — avoids long prompts in expo-router params. */
import type { QuizVariant } from "@/lib/quizVariant";

export type QueuedLessonLaunch = {
  projectId: string;
  prompt?: string;
  quizLanguage?: string;
  quizVariant?: QuizVariant;
};

let queued: QueuedLessonLaunch | null = null;

export function queueLessonLaunch(launch: QueuedLessonLaunch): boolean {
  const projectId = launch.projectId.trim();
  if (!projectId) return false;
  const prompt = launch.prompt?.trim();
  queued = {
    projectId,
    ...(prompt ? { prompt } : {}),
    ...(launch.quizLanguage ? { quizLanguage: launch.quizLanguage } : {}),
    ...(launch.quizVariant ? { quizVariant: launch.quizVariant } : {}),
  };
  return true;
}

export function takeQueuedLessonLaunch(): QueuedLessonLaunch | null {
  if (!queued) return null;
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

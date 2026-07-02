/** Queued chat opener — avoids fragile long strings in expo-router params. */
export type QueuedChatLaunch = {
  prompt: string;
  projectId?: string;
  quizLanguage?: string;
};

let queued: QueuedChatLaunch | null = null;

export function queueChatLaunch(
  prompt: string,
  projectId?: string,
  quizLanguage?: string,
): boolean {
  const trimmed = prompt.trim();
  if (!trimmed) return false;
  queued = {
    prompt: trimmed,
    ...(projectId ? { projectId } : {}),
    ...(quizLanguage ? { quizLanguage } : {}),
  };
  return true;
}

export function takeQueuedChatLaunch(): QueuedChatLaunch | null {
  if (!queued) return null;
  const next = queued;
  queued = null;
  return next;
}

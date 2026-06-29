/** Queued chat opener — avoids fragile long strings in expo-router params. */
export type QueuedChatLaunch = {
  prompt: string;
  projectId?: string;
};

let queued: QueuedChatLaunch | null = null;

export function queueChatLaunch(prompt: string, projectId?: string): void {
  const trimmed = prompt.trim();
  if (!trimmed) return;
  queued = { prompt: trimmed, ...(projectId ? { projectId } : {}) };
}

export function takeQueuedChatLaunch(): QueuedChatLaunch | null {
  if (!queued) return null;
  const next = queued;
  queued = null;
  return next;
}

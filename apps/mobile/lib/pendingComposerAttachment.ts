import type { PendingAttachment } from "@/lib/attachments";

let queued: PendingAttachment | null = null;
const listeners = new Set<() => void>();

/** Hand a Library pick to the composer (index stays mounted under /gallery). */
export function queueComposerAttachment(pending: PendingAttachment): void {
  queued = pending;
  for (const listener of listeners) listener();
}

export function takeQueuedComposerAttachment(): PendingAttachment | null {
  const next = queued;
  queued = null;
  return next;
}

export function subscribeComposerAttachmentQueue(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Test helper. */
export function resetComposerAttachmentQueue(): void {
  queued = null;
}

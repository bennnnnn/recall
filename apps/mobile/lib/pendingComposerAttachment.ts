import { getSessionGeneration } from "@/lib/auth";
import type { PendingAttachment } from "@/lib/attachments";

type Queued = { pending: PendingAttachment; session: number; thread?: string };
let queued: Queued | null = null;
const listeners = new Set<() => void>();

/** Hand a Library pick to the intended composer in the same account session. */
export function queueComposerAttachment(pending: PendingAttachment, thread?: string): void {
  queued = { pending, thread, session: getSessionGeneration() };
  for (const listener of listeners) listener();
}
export function takeQueuedComposerAttachment(thread?: string): PendingAttachment | null {
  if (queued?.session !== getSessionGeneration()) queued = null;
  if (!queued || (queued.thread && queued.thread !== thread)) return null;
  const next = queued.pending;
  queued = null;
  return next;
}
export function subscribeComposerAttachmentQueue(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
/** Test helper. */
export function resetComposerAttachmentQueue(): void { queued = null; }

/**
 * A memory edit this phone sent that did not answer may still be saving: the server keeps
 * working, under the memory lock, after the phone stops waiting. A retry then meets that
 * lock (409 `memory_busy`), which is the first edit landing, not a failure, so for a while
 * after an unanswered edit the phone says "still saving" (security review, 2026-11-25).
 */
import type { MemoryFailure } from "@/features/memory/model/memoryFailure";

/** How long after an unanswered edit a busy memory is that edit still saving. */
export const STILL_SAVING_MS = 90_000;

/**
 * What an edit's failure means, given when an earlier edit from here went unanswered
 * (`unansweredAt`, or null): a busy memory soon after one is that edit still saving.
 */
export function instructFailure(
  failure: MemoryFailure,
  unansweredAt: number | null,
  now = Date.now(),
): MemoryFailure {
  if (failure !== "busy" || unansweredAt === null) return failure;
  return now - unansweredAt < STILL_SAVING_MS ? "saving" : failure;
}

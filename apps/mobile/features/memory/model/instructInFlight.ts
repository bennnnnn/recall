/**
 * A memory edit this phone sent that did not answer may still be saving: the server keeps
 * working, under the memory lock, after the phone stops waiting. A retry then meets that
 * lock (409 `memory_busy`), which is the first edit landing, not a failure, so for a while
 * after an unanswered edit the phone says "still saving" (security review, 2026-11-25).
 */
import type { MemoryFailure } from "@/features/memory/model/memoryFailure";
import { isAbortError } from "@/lib/api/abort";
import { getSessionGeneration } from "@/lib/auth";

/** How long after an unanswered edit a busy memory is that edit still saving. */
export const STILL_SAVING_MS = 90_000;

/**
 * Whether an edit that failed may still be saving: it was sent and its wait ran out (the
 * request's own deadline aborts it). A send that never connected (offline, a refused
 * connection) reached nothing, so a busy memory after it is some other write.
 */
export function mayStillBeSaving(error: unknown): boolean {
  return isAbortError(error);
}

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

// This phone's last unanswered edit, by the sign-in that sent it. Shared by every memory
// screen and kept across a remount: an edit from the list retried from a page (or after
// leaving Memory) still meets its own edit. Another sign-in never reads it.
let unanswered: { at: number; generation: number } | null = null;

/** The edit went out and its wait ran out (`mayStillBeSaving`): it may land after. */
export function noteInstructUnanswered(now = Date.now()): void {
  unanswered = { at: now, generation: getSessionGeneration() };
}

/** An edit answered: nothing of this phone's is left saving. */
export function noteInstructAnswered(): void {
  unanswered = null;
}

/** When this sign-in's last edit went unanswered, or null. */
export function unansweredSince(): number | null {
  return unanswered && unanswered.generation === getSessionGeneration() ? unanswered.at : null;
}

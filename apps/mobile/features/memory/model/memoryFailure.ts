import { ApiRequestError } from "@/lib/api/errorBody";

/** Why a memory change did not happen, in the terms the person who asked needs. */
export type MemoryFailure = "busy" | "off" | "gone" | "limited" | "unreachable" | "failed";

/** A memory change: done, or why not. */
export type MemoryChange = { ok: true } | { ok: false; failure: MemoryFailure };

/**
 * Reads a failed memory request. Every failure used to be one "couldn't be updated",
 * so a write that met another write looked broken and memory turned off looked like a
 * bug (code-health audit CLAR-08). The server names its refusals (DUP-10).
 */
export function memoryFailure(error: unknown): MemoryFailure {
  if (!(error instanceof ApiRequestError)) return "unreachable";
  if (error.code === "memory_busy") return "busy";
  if (error.code === "memory_off") return "off";
  if (error.code === "rate_limited") return "limited";
  if (error.status === 404) return "gone";
  return "failed";
}

const FAILURE_KEYS: Record<Exclude<MemoryFailure, "failed">, string> = {
  busy: "memory.busy",
  off: "memory.off",
  gone: "memory.document_gone",
  limited: "memory.limited",
  unreachable: "common.api_unreachable",
};

/** What to say: the failure's own words, else the action's ("Couldn't delete. Try again."). */
export function memoryFailureKey(failure: MemoryFailure, actionKey: string): string {
  return failure === "failed" ? actionKey : FAILURE_KEYS[failure];
}

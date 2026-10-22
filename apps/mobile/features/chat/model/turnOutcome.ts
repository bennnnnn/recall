// Types only: the reporter loads lazily once the turn has ended.
import type { ChatTurnOutcomeProperties } from "@/features/chat/model/latencyReporter";
import { sampleChatEvent } from "@/features/chat/model/chatEventSample";

/**
 * How each chat turn ended, as the metadata-only `chat_turn_outcome` event:
 * complete, stopped, interrupted or failed, the error code, and the first
 * tool it showed working. Never the prompt, the reply, a query or a message;
 * every value comes from the lists below or the server's own enumerations.
 */

/** Stream status phases that are real tool work (stream_status.StreamStatusPhase). */
const TOOL_PHASES = new Set([
  "searching",
  "calculating",
  "physics",
  "chemistry",
  "reading_files",
  "finding_photo",
  "image_gen",
]);

/** Error frame codes the server sends (stream_events.error_payload_for_exception). */
const ERROR_CODES = new Set([
  "quota_exceeded",
  "spend_cap",
  "model_unavailable",
  "unavailable",
  "busy",
  "attachment_rejected",
  "unknown_model",
  "rate_limited",
]);

type Completion = ChatTurnOutcomeProperties["completion"];

// One turn streams at a time; `start` opens it and its first ending reports it.
let open = false;
let tool = "none";
let sampled = false;

/** The server took a turn (`start`). */
export function beginTurnOutcome(): void {
  open = true;
  tool = "none";
  sampled = sampleChatEvent();
}

/** A `status` frame: the first tool phase is the turn's tool. */
export function noteTurnActivity(phase: string): void {
  if (open && tool === "none" && TOOL_PHASES.has(phase)) tool = phase;
}

/** The `done` frame's completion, as the event names it. */
export function completionFromDone(completion: string | undefined): Completion {
  if (completion === "user_stop") return "stopped";
  if (completion === "interrupted") return "interrupted";
  return "complete";
}

export function turnOutcomeProperties(
  completion: Completion,
  errorCode?: string,
): ChatTurnOutcomeProperties {
  const code = completion !== "error" ? "none" : errorCode && ERROR_CODES.has(errorCode) ? errorCode : "other";
  return { completion, error_code: code, tool };
}

/** Report the open turn once (a later frame of the same turn reports nothing). */
export function reportTurnOutcome(completion: Completion, errorCode?: string): void {
  if (!open) return;
  open = false;
  const properties = turnOutcomeProperties(completion, errorCode);
  if (!sampled) return;
  void import("@/features/chat/model/latencyReporter")
    .then(({ reportChatTurnOutcome }) => reportChatTurnOutcome(properties))
    .catch(() => {
      // Product telemetry is best-effort and must never affect chat.
    });
}

// Types only: the reporter module itself still loads lazily after the first token.
import type { ChatTransport, ChatTtftBucket } from "@/features/chat/model/latencyReporter";
import { sampleChatEvent } from "@/features/chat/model/chatEventSample";

type PendingChatTtft = {
  turnId: string;
  startedAtMs: number;
  transport: ChatTransport;
  hasAttachment: boolean;
};

let pending: PendingChatTtft | null = null;

/** Bucket user-bubble -> first-token latency without storing arbitrary timing values. */
export function chatTtftBucket(elapsedMs: number): ChatTtftBucket {
  const ms = Number.isFinite(elapsedMs) ? Math.max(0, elapsedMs) : 0;
  if (ms < 500) return "lt500";
  if (ms < 1_000) return "500_999";
  if (ms < 2_000) return "1000_1999";
  if (ms < 4_000) return "2000_3999";
  if (ms < 6_000) return "4000_5999";
  return "6000_plus";
}

/**
 * Start when the optimistic user bubble is created. This happens before file
 * upload, draft-chat creation, transport connection, backend prep, and model
 * inference, so the sample captures nearly all latency the user actually sees.
 *
 * `turnId` is the optimistic user-message id. Leftover SSE from a previous
 * chat must not stamp or consume a later send's sample.
 */
export function markChatTtftStart(
  turnId: string,
  createdAt: string,
  hasAttachment: boolean,
): void {
  // A sampled turn only; any earlier unfinished sample is dropped either way.
  pending = null;
  if (!turnId || !sampleChatEvent()) return;
  const parsed = Date.parse(createdAt);
  pending = {
    turnId,
    startedAtMs: Number.isFinite(parsed) ? parsed : Date.now(),
    transport: "ws",
    hasAttachment,
  };
}

/** SSE is a fallback; the optimistic default is WebSocket until this is called. */
export function markChatTtftTransport(turnId: string | null | undefined, transport: ChatTransport): void {
  if (!pending || !turnId || pending.turnId !== turnId) return;
  pending.transport = transport;
}

/**
 * Record at most once, on the first actual answer token accepted for this
 * originating stream. Leftover parse of another chat's SSE must not match.
 */
export function markChatFirstToken(
  turnId: string | null | undefined,
  payloadType: string,
): void {
  if (payloadType !== "token" || !pending || !turnId || pending.turnId !== turnId) return;
  const sample = pending;
  pending = null;
  const elapsedMs = Math.max(0, Date.now() - sample.startedAtMs);

  // Reporter is intentionally lazy and fire-and-forget: loading analytics,
  // SecureStore, app metadata, and installation id happens only after the first
  // token is already on its way to the UI, so telemetry cannot worsen TTFT.
  void import("@/features/chat/model/latencyReporter")
    .then(({ reportChatTtft }) =>
      reportChatTtft({
        latencyBucket: chatTtftBucket(elapsedMs),
        transport: sample.transport,
        hasAttachment: sample.hasAttachment,
      }),
    )
    .catch(() => {
      // Product telemetry is best-effort and must never affect chat.
    });
}

/** Drop an unfinished sample. Omit `turnId` to discard whatever is pending. */
export function clearPendingChatTtft(turnId?: string | null): void {
  if (turnId != null && pending?.turnId !== turnId) return;
  pending = null;
}

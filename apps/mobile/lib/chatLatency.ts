export type ChatTtftBucket =
  | "lt500"
  | "500_999"
  | "1000_1999"
  | "2000_3999"
  | "4000_5999"
  | "6000_plus";

export type ChatTransport = "ws" | "sse";

type PendingChatTtft = {
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
 */
export function markChatTtftStart(createdAt: string, hasAttachment: boolean): void {
  // Metro defines __DEV__, but plain Jest/Node does not. `typeof` keeps this
  // production-only measurement safe in both runtimes without test globals.
  if (typeof __DEV__ !== "undefined" && __DEV__) return;
  const parsed = Date.parse(createdAt);
  pending = {
    startedAtMs: Number.isFinite(parsed) ? parsed : Date.now(),
    transport: "ws",
    hasAttachment,
  };
}

/** SSE is a fallback; the optimistic default is WebSocket until this is called. */
export function markChatTtftTransport(transport: ChatTransport): void {
  if (!pending) return;
  pending.transport = transport;
}

/** Record at most once, on the first actual answer token. */
export function markChatFirstToken(payloadType: string): void {
  if (payloadType !== "token" || !pending) return;
  const sample = pending;
  pending = null;
  const elapsedMs = Math.max(0, Date.now() - sample.startedAtMs);

  // Reporter is intentionally lazy and fire-and-forget: loading analytics,
  // SecureStore, app metadata, and installation id happens only after the first
  // token is already on its way to the UI, so telemetry cannot worsen TTFT.
  void import("@/lib/chatLatencyReporter")
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

/** Tests and session resets may explicitly discard an unfinished sample. */
export function clearPendingChatTtft(): void {
  pending = null;
}

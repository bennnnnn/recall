import { useCallback, useMemo, useRef } from "react";
import { randomUUID } from "expo-crypto";

import { shouldAbortPriorSse } from "@/features/chat/model/sse";
import { api } from "@/lib/api";
import { reportFailure } from "@/lib/sentry";

/** The user's Stop, with how much of the reply the phone drew (as on the socket's cancel). */
type SseStop = { shownChars?: number };

/** How long a Stop waits for the server to hear it before the stream closes anyway. */
export const SSE_STOP_SAY_MS = 2_000;

/** One SSE stream: what closes it, and the name its Stop says it by. */
type SseStream = { signal: AbortSignal; streamId: string };

/**
 * The one SSE stream a chat view has in flight. Closing it is not a Stop: the server
 * finishes and saves a reply whose stream only closed (a dropped connection), as it does
 * a socket's. Each stream is named (`stream_id`), and the user's Stop is said for that
 * stream (`POST /chats/{id}/stream/stop`) before it closes: once the server has it, or
 * after `SSE_STOP_SAY_MS` on a slow network or a token refresh.
 */
export function useSseStream(chatId: string | null, getToken: () => string | null) {
  const controllerRef = useRef<AbortController | null>(null);
  const chatIdRef = useRef<string | null>(null);
  const streamIdRef = useRef<string | null>(null);

  /** A new stream for this chat; one still open for the same chat closes. */
  const begin = useCallback((): SseStream => {
    if (shouldAbortPriorSse(chatIdRef.current, chatId)) controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    chatIdRef.current = chatId;
    streamIdRef.current = randomUUID();
    return { signal: controller.signal, streamId: streamIdRef.current };
  }, [chatId]);

  const isCurrent = useCallback((signal: AbortSignal) => controllerRef.current?.signal === signal, []);

  /** Forget the stream in flight without closing it (leaving the chat lets it finish). */
  const forget = useCallback(() => {
    controllerRef.current = null;
    chatIdRef.current = null;
    streamIdRef.current = null;
  }, []);

  /** The stream behind `signal` ended: false when another has taken its place. */
  const end = useCallback((signal: AbortSignal) => {
    if (!isCurrent(signal)) return false;
    forget();
    return true;
  }, [forget, isCurrent]);

  /** Close the stream in flight; `stop`: the user's Stop, said to the server first. The
   * stream stops being current at once (its late frames are dropped). */
  const abort = useCallback((stop?: SseStop) => {
    const controller = controllerRef.current;
    const sseChatId = chatIdRef.current;
    const streamId = streamIdRef.current;
    const token = getToken();
    controllerRef.current = null;
    if (!controller) return;
    if (!stop || !sseChatId || !streamId || !token) {
      controller.abort();
      return;
    }
    const said = api.stopChatStream(token, sseChatId, streamId, stop.shownChars).catch((error: unknown) => {
      // The stream then closes as a drop: the reply saves whole.
      reportFailure("chat_stop", error);
    });
    let timer: ReturnType<typeof setTimeout> | undefined;
    const waited = new Promise<void>((resolve) => { timer = setTimeout(resolve, SSE_STOP_SAY_MS); });
    void Promise.race([said, waited]).then(() => {
      clearTimeout(timer);
      controller.abort();
    });
  }, [getToken]);

  return useMemo(() => ({ begin, isCurrent, end, forget, abort }), [begin, isCurrent, end, forget, abort]);
}

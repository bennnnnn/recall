import { useCallback, useMemo, useRef } from "react";

import { shouldAbortPriorSse } from "@/features/chat/model/sse";
import { api } from "@/lib/api";
import { reportFailure } from "@/lib/sentry";

/** The user's Stop, with how much of the reply the phone drew (as on the socket's cancel). */
type SseStop = { shownChars?: number };

/**
 * The one SSE stream a chat view has in flight. Closing it is not a Stop: the server
 * finishes and saves a reply whose stream only closed (a dropped connection), as it does
 * a socket's. The user's Stop is said to the server first (`POST /chats/{id}/stream/stop`),
 * then the stream closes.
 */
export function useSseStream(chatId: string | null, getToken: () => string | null) {
  const controllerRef = useRef<AbortController | null>(null);
  const chatIdRef = useRef<string | null>(null);

  /** A new stream for this chat; one still open for the same chat closes. */
  const begin = useCallback(() => {
    if (shouldAbortPriorSse(chatIdRef.current, chatId)) controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    chatIdRef.current = chatId;
    return controller.signal;
  }, [chatId]);

  const isCurrent = useCallback((signal: AbortSignal) => controllerRef.current?.signal === signal, []);

  /** Forget the stream in flight without closing it (leaving the chat lets it finish). */
  const forget = useCallback(() => {
    controllerRef.current = null;
    chatIdRef.current = null;
  }, []);

  /** The stream behind `signal` ended: false when another has taken its place. */
  const end = useCallback((signal: AbortSignal) => {
    if (!isCurrent(signal)) return false;
    forget();
    return true;
  }, [forget, isCurrent]);

  /** Close the stream in flight; `stop`: the user's Stop, said to the server first. */
  const abort = useCallback((stop?: SseStop) => {
    const token = getToken();
    if (stop && controllerRef.current && chatIdRef.current && token) {
      void api.stopChatStream(token, chatIdRef.current, stop.shownChars).catch((error: unknown) => {
        // The stream then closes as a drop: the reply saves whole.
        reportFailure("chat_stop", error);
      });
    }
    controllerRef.current?.abort();
    controllerRef.current = null;
  }, [getToken]);

  return useMemo(() => ({ begin, isCurrent, end, forget, abort }), [begin, isCurrent, end, forget, abort]);
}

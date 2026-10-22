import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
} from "react";

import type { StreamingDraft } from "@/lib/streamingDraftStore";

/**
 * After `stream_end` a reply's text is all here and only its save is left, which
 * takes a tenth of a second; the server stops waiting on it after 10 s and sends
 * `done` anyway (stream_events.DONE_COMMIT_WAIT_SECONDS). A send still waiting
 * past this leaves that quiet connection and reloads the chat for the saved
 * reply, as after a drop, rather than wait on it.
 */
export const REPLY_SAVE_GRACE_MS = 12_000;

/** Typing dots one send raised with its bubble, before the send went out. */
export type DotsTicket = {
  /** Still this send's: no Stop, other turn or other view has taken them down. */
  current: () => boolean;
  /**
   * Takes these dots down: the send went to image generation, or nowhere. A
   * no-op once they are not this send's, so a late call (say from a chat the
   * user has left) never touches another send's dots.
   */
  cancel: () => void;
};

/** What the composer sees of a turn before it goes out. */
export type SendTurnStart = {
  /**
   * Typing dots under a bubble just painted, in the same frame. Null when they
   * cannot go up yet: no chat is open, or a reply is still streaming or saving.
   */
  beginDots: () => DotsTicket | null;
  /**
   * Resolves once no reply streams or saves: a send made after the last reply's
   * `stream_end` goes out after its `done`, so that `done` never lands on the new
   * turn. `waitingId` is the bubble that waits; it says "Sending" after a beat.
   */
  whenReplySettled: (waitingId?: string) => Promise<void>;
};

type Options = {
  canStart: boolean;
  isCurrentView: () => boolean;
  streaming: boolean;
  finalizing: boolean;
  streamingRef: MutableRefObject<boolean>;
  finalizingRef: MutableRefObject<boolean>;
  sendAttemptRef: MutableRefObject<number>;
  stoppedStreamedIdRef: MutableRefObject<string | null>;
  setStreaming: Dispatch<SetStateAction<boolean>>;
  setSendingMessageId: Dispatch<SetStateAction<string | null>>;
  updateStreamingDraft: (draft: StreamingDraft | null) => void;
  appendStreamingPlaceholder: () => void;
  clearStreamingBubble: () => void;
  dropSocket: () => void;
  /** A saving reply whose `done` never came: leave its connection and reload the chat for it. */
  settleUnconfirmedReply: () => void;
};

/**
 * How a turn starts on screen: typing dots, either with the dispatch or (for the
 * composer) with the bubble before the send has gone out; a fresh connection
 * after Stop so the stopped turn's late frames reach nothing; and the wait for
 * a reply that is only saving, which Send no longer has to sit out.
 */
export function useTurnStart({
  canStart,
  isCurrentView,
  streaming,
  finalizing,
  streamingRef,
  finalizingRef,
  sendAttemptRef,
  stoppedStreamedIdRef,
  setStreaming,
  setSendingMessageId,
  updateStreamingDraft,
  appendStreamingPlaceholder,
  clearStreamingBubble,
  dropSocket,
  settleUnconfirmedReply,
}: Options) {
  /** The attempt whose dots went up before its send was dispatched. */
  const earlyDotsRef = useRef<number | null>(null);
  const settleWaitersRef = useRef<(() => void)[]>([]);
  const graceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Read when the grace runs out, so the wait itself stays one stable callback.
  const settleRef = useRef(settleUnconfirmedReply);
  settleRef.current = settleUnconfirmedReply;

  const releaseWaiters = useCallback(() => {
    if (graceTimerRef.current != null) clearTimeout(graceTimerRef.current);
    graceTimerRef.current = null;
    const waiters = settleWaitersRef.current;
    settleWaitersRef.current = [];
    for (const resolve of waiters) resolve();
  }, []);

  // Every way a reply ends (done, an error, a drop, Stop, another view) leaves
  // both false; a waiter then checks for itself whether its send still stands.
  useEffect(() => {
    if (!streaming && !finalizing) releaseWaiters();
  }, [streaming, finalizing, releaseWaiters]);
  useEffect(() => releaseWaiters, [releaseWaiters]);

  const whenReplySettled = useCallback((waitingId?: string) => {
    if (!streamingRef.current && !finalizingRef.current) return Promise.resolve();
    if (waitingId) setSendingMessageId(waitingId);
    graceTimerRef.current ??= setTimeout(() => {
      graceTimerRef.current = null;
      if (finalizingRef.current && isCurrentView()) settleRef.current();
    }, REPLY_SAVE_GRACE_MS);
    return new Promise<void>((resolve) => {
      settleWaitersRef.current.push(resolve);
    });
  }, [streamingRef, finalizingRef, setSendingMessageId, isCurrentView]);

  const showDots = useCallback((status?: string) => {
    setStreaming(true);
    streamingRef.current = true;
    setSendingMessageId(null);
    updateStreamingDraft({ content: "", status });
    appendStreamingPlaceholder();
  }, [setStreaming, streamingRef, setSendingMessageId, updateStreamingDraft, appendStreamingPlaceholder]);

  /** Stop may still have a final frame in flight; a new connection keeps it off the next turn. */
  const leaveStoppedTurn = useCallback(() => {
    if (!stoppedStreamedIdRef.current) return;
    dropSocket();
    stoppedStreamedIdRef.current = null;
  }, [stoppedStreamedIdRef, dropSocket]);

  const beginDots = useCallback((): DotsTicket | null => {
    if (!canStart || !isCurrentView() || streamingRef.current || finalizingRef.current) return null;
    const attempt = ++sendAttemptRef.current;
    earlyDotsRef.current = attempt;
    leaveStoppedTurn();
    showDots();
    const current = () => isCurrentView() && sendAttemptRef.current === attempt;
    const cancel = () => {
      if (earlyDotsRef.current === attempt) earlyDotsRef.current = null;
      if (!current()) return;
      sendAttemptRef.current += 1;
      setStreaming(false);
      streamingRef.current = false;
      clearStreamingBubble();
    };
    return { current, cancel };
  }, [
    canStart, isCurrentView, streamingRef, finalizingRef, sendAttemptRef, leaveStoppedTurn, showDots, setStreaming,
    clearStreamingBubble,
  ]);

  /** True when the dots up now are this dispatch's (the attempt that raised them is still the latest). */
  const takeEarlyDots = useCallback(() => {
    const mine = earlyDotsRef.current !== null && earlyDotsRef.current === sendAttemptRef.current;
    if (mine) earlyDotsRef.current = null;
    return mine;
  }, [sendAttemptRef]);

  const sendStart = useMemo<SendTurnStart>(
    () => ({ beginDots, whenReplySettled }),
    [beginDots, whenReplySettled],
  );
  return { showDots, leaveStoppedTurn, takeEarlyDots, sendStart };
}

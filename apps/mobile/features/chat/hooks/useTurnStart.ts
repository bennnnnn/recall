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
 * past this settles the reply itself rather than wait on a connection gone quiet.
 */
export const REPLY_SAVE_GRACE_MS = 12_000;

/** What the composer sees of a turn before it goes out. */
export type SendTurnStart = {
  /**
   * Typing dots under a bubble just painted, in the same frame. The guard turns
   * false once Stop, another turn or a new view takes them down. Null when they
   * cannot go up yet: no chat is open, or a reply is still streaming or saving.
   */
  beginDots: () => (() => boolean) | null;
  /** Takes the dots down: the send went to image generation, or nowhere. */
  cancelDots: () => void;
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
  /** Settle a saving reply as its `done` would without an id, the server's own fallback. */
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

  const beginDots = useCallback(() => {
    if (!canStart || !isCurrentView() || streamingRef.current || finalizingRef.current) return null;
    const attempt = ++sendAttemptRef.current;
    earlyDotsRef.current = attempt;
    leaveStoppedTurn();
    showDots();
    return () => isCurrentView() && sendAttemptRef.current === attempt;
  }, [canStart, isCurrentView, streamingRef, finalizingRef, sendAttemptRef, leaveStoppedTurn, showDots]);

  const cancelDots = useCallback(() => {
    const attempt = earlyDotsRef.current;
    earlyDotsRef.current = null;
    if (attempt === null || attempt !== sendAttemptRef.current || !isCurrentView()) return;
    sendAttemptRef.current += 1;
    setStreaming(false);
    streamingRef.current = false;
    clearStreamingBubble();
  }, [sendAttemptRef, isCurrentView, setStreaming, streamingRef, clearStreamingBubble]);

  /** True when this send's dots are already up: its dispatch keeps them. */
  const takeEarlyDots = useCallback(() => {
    const attempt = earlyDotsRef.current;
    earlyDotsRef.current = null;
    return attempt !== null && attempt === sendAttemptRef.current;
  }, [sendAttemptRef]);

  const sendStart = useMemo<SendTurnStart>(
    () => ({ beginDots, cancelDots, whenReplySettled }),
    [beginDots, cancelDots, whenReplySettled],
  );
  return { showDots, leaveStoppedTurn, takeEarlyDots, sendStart };
}

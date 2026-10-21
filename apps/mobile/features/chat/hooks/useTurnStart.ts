import {
  useCallback,
  useMemo,
  useRef,
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
} from "react";

import type { StreamingDraft } from "@/lib/streamingDraftStore";

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
};

type Options = {
  canStart: boolean;
  isCurrentView: () => boolean;
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
};

/**
 * How a turn starts on screen: typing dots, either with the dispatch or (for the
 * composer) with the bubble before the send has gone out, and a fresh
 * connection after Stop so the stopped turn's late frames reach nothing.
 */
export function useTurnStart({
  canStart,
  isCurrentView,
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
}: Options) {
  /** The attempt whose dots went up before its send was dispatched. */
  const earlyDotsRef = useRef<number | null>(null);

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

  const sendStart = useMemo<SendTurnStart>(() => ({ beginDots, cancelDots }), [beginDots, cancelDots]);
  return { showDots, leaveStoppedTurn, takeEarlyDots, sendStart };
}

import { useCallback, useEffect, useRef, useState } from "react";
import type { NativeScrollEvent, NativeSyntheticEvent } from "react-native";
import type { FlashListRef } from "@shopify/flash-list";

import { getStreamingDraftContentLength, subscribeStreamingDraft } from "@/lib/streamingDraftStore";
import type { Message } from "@/lib/api";
import {
  getScrollThresholds,
  nextStreamingScrollDelay,
  resolveScrollAtBottom,
  shouldSchedulePostStreamScroll,
} from "@/lib/chatScrollLogic";
import { STREAM_LAYOUT_SETTLE_MS } from "@/lib/messageListLayout";
import { clearScheduledTimeout, scheduleTimeout } from "@/lib/scheduleTimeout";
import { tap } from "@/lib/haptics";

/**
 * While streaming, JS owns bottom-pinning (FlashList autoscroll is off).
 * This is a throttle interval, not a debounce: `scheduleTimeout` clears and
 * restarts on every call, so a plain debounce here would never fire while
 * draft updates keep arriving faster than this interval (normal for a fast
 * provider) — the view would sit frozen through the stream and only catch
 * up once generation paused. `scheduleStreamingScroll` re-derives the
 * remaining wait from elapsed time so it still fires on a steady cadence.
 */
const STREAMING_SCROLL_THROTTLE_MS = 64;
/** Skip catch-up when already within a few pixels of the bottom. */
const STREAMING_SCROLL_SLACK_PX = 8;

type Options = {
  chatId: string | null;
  messagesLength: number;
  streamActive: boolean;
  windowHeight: number;
  keyboardHeight: number;
};

export function useChatScroll({
  chatId,
  messagesLength,
  streamActive,
  windowHeight,
  keyboardHeight,
}: Options) {
  const listRef = useRef<FlashListRef<Message>>(null);
  const atBottomRef = useRef(true);
  const newMessageCountRef = useRef(0);
  const showScrollBtnRef = useRef(false);
  const messagesLenRef = useRef(0);
  const listBottomPadRef = useRef(0);
  const maxScrollOffsetRef = useRef(0);
  const scrollOffsetRef = useRef(0);
  const viewportHeightRef = useRef(0);
  const streamingScrollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const streamingScrollLastRunRef = useRef(0);
  const streamEndScrollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const keyboardScrollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prevStreamActiveRef = useRef(false);
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);
  const [scrollAwayCount, setScrollAwayCount] = useState(0);

  messagesLenRef.current = messagesLength;

  const updateAtBottom = useCallback((atBottom: boolean) => {
    atBottomRef.current = atBottom;
    const shouldShow = !atBottom && messagesLenRef.current > 0;
    if (shouldShow === showScrollBtnRef.current) return;
    showScrollBtnRef.current = shouldShow;
    setShowScrollToBottom(shouldShow);
    if (!shouldShow) setScrollAwayCount(0);
  }, []);

  const measureScrollMetrics = useCallback(
    (event?: NativeSyntheticEvent<NativeScrollEvent>) => {
      if (event) {
        const { contentOffset, contentSize, layoutMeasurement } = event.nativeEvent;
        const viewportHeight = layoutMeasurement.height;
        const contentHeight = contentSize.height;
        const scrollY = contentOffset.y;
        scrollOffsetRef.current = scrollY;
        if (viewportHeight > 0) viewportHeightRef.current = viewportHeight;
        if (viewportHeight <= 0 || contentHeight <= 0) return null;
        const maxOffset = Math.max(0, contentHeight - viewportHeight);
        maxScrollOffsetRef.current = maxOffset;
        return { distanceFromBottom: maxOffset - scrollY, maxOffset };
      }

      const list = listRef.current;
      if (!list) return null;
      try {
        const scrollOffset = list.getAbsoluteLastScrollOffset();
        scrollOffsetRef.current = scrollOffset;
        const contentSize = list.getChildContainerDimensions();
        const windowSize = list.getWindowSize();
        const viewportHeight = windowSize.height;
        const contentHeight = contentSize.height;
        if (viewportHeight > 0) viewportHeightRef.current = viewportHeight;
        if (viewportHeight <= 0 || contentHeight <= 0) return null;
        const maxOffset = Math.max(0, contentHeight - viewportHeight);
        maxScrollOffsetRef.current = maxOffset;
        return { distanceFromBottom: maxOffset - scrollOffset, maxOffset };
      } catch {
        return null;
      }
    },
    [],
  );

  const readScrollThresholds = useCallback(() => {
    return getScrollThresholds({
      viewportHeight: viewportHeightRef.current,
      windowHeight,
      listBottomPad: listBottomPadRef.current,
    });
  }, [windowHeight]);

  const syncScrollPosition = useCallback(
    (event?: NativeSyntheticEvent<NativeScrollEvent>) => {
      if (messagesLenRef.current === 0) {
        updateAtBottom(true);
        return;
      }
      const metrics = measureScrollMetrics(event);
      if (!metrics) return;
      if (metrics.maxOffset <= 0) {
        updateAtBottom(true);
        return;
      }
      const { hideAtBottom, showWhenAway } = readScrollThresholds();
      const nextAtBottom = resolveScrollAtBottom({
        distanceFromBottom: metrics.distanceFromBottom,
        hideAtBottom,
        showWhenAway,
        currentlyAtBottom: atBottomRef.current,
      });
      updateAtBottom(nextAtBottom);
    },
    [readScrollThresholds, measureScrollMetrics, updateAtBottom],
  );

  const scrollToEndIfAtBottom = useCallback((animated: boolean) => {
    if (!atBottomRef.current) return;
    listRef.current?.scrollToEnd({ animated });
  }, []);

  const runStreamingScrollCatchUp = useCallback(() => {
    streamingScrollLastRunRef.current = Date.now();
    if (atBottomRef.current) {
      // During streaming, FlashList autoscroll is disabled (see ChatMessageList)
      // so this is the sole bottom-pin writer. Use animated catch-up — hard
      // snaps at LLM burst boundaries read as up/down jitter.
      const metrics = measureScrollMetrics();
      if (metrics && metrics.distanceFromBottom <= STREAMING_SCROLL_SLACK_PX) {
        return;
      }
      listRef.current?.scrollToEnd({ animated: true });
    } else {
      requestAnimationFrame(() => syncScrollPosition());
    }
  }, [measureScrollMetrics, syncScrollPosition]);

  const scheduleStreamingScroll = useCallback(() => {
    const elapsed = Date.now() - streamingScrollLastRunRef.current;
    const delay = nextStreamingScrollDelay(elapsed, STREAMING_SCROLL_THROTTLE_MS);
    if (delay <= 0) {
      clearScheduledTimeout(streamingScrollTimerRef);
      runStreamingScrollCatchUp();
      return;
    }
    // Trailing call for the tail of a burst — rescheduled on every call, but
    // `delay` shrinks toward 0 as elapsed time grows, so the target fire time
    // converges instead of being pushed out on every new update.
    scheduleTimeout(streamingScrollTimerRef, delay, runStreamingScrollCatchUp);
  }, [runStreamingScrollCatchUp]);

  const schedulePostStreamScroll = useCallback(() => {
    scheduleTimeout(streamEndScrollTimerRef, STREAM_LAYOUT_SETTLE_MS, () => {
      if (atBottomRef.current) {
        listRef.current?.scrollToEnd({ animated: false });
      }
    });
  }, []);

  useEffect(() => {
    if (messagesLength > 0 && newMessageCountRef.current > 0) {
      const pending = newMessageCountRef.current;
      newMessageCountRef.current = 0;
      if (atBottomRef.current) {
        listRef.current?.scrollToEnd({ animated: true });
      } else {
        setScrollAwayCount((c) => c + pending);
        showScrollBtnRef.current = true;
        setShowScrollToBottom(true);
      }
    }
  }, [messagesLength]);

  useEffect(() => {
    const wasStreamActive = prevStreamActiveRef.current;
    prevStreamActiveRef.current = streamActive;

    if (!streamActive) {
      if (shouldSchedulePostStreamScroll(wasStreamActive, streamActive, atBottomRef.current)) {
        schedulePostStreamScroll();
      }
      return;
    }

    const syncStreamingScroll = () => {
      if (getStreamingDraftContentLength() > 0) {
        scheduleStreamingScroll();
      }
    };

    syncStreamingScroll();
    return subscribeStreamingDraft(syncStreamingScroll);
  }, [streamActive, scheduleStreamingScroll, schedulePostStreamScroll]);

  useEffect(() => {
    requestAnimationFrame(() => syncScrollPosition());
  }, [messagesLength, syncScrollPosition]);

  useEffect(() => {
    maxScrollOffsetRef.current = 0;
    scrollOffsetRef.current = 0;
    viewportHeightRef.current = 0;
    showScrollBtnRef.current = false;
    setShowScrollToBottom(false);
    setScrollAwayCount(0);
    atBottomRef.current = true;
    streamingScrollLastRunRef.current = 0;
  }, [chatId]);

  useEffect(() => {
    return () => {
      clearScheduledTimeout(streamingScrollTimerRef);
      clearScheduledTimeout(streamEndScrollTimerRef);
      clearScheduledTimeout(keyboardScrollTimerRef);
    };
  }, []);

  const scrollToLatest = useCallback(() => {
    tap();
    listRef.current?.scrollToEnd({ animated: true });
    updateAtBottom(true);
  }, [updateAtBottom]);

  const handleScroll = useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>) => {
      syncScrollPosition(event);
    },
    [syncScrollPosition],
  );

  const handleScrollEnd = useCallback(() => {
    syncScrollPosition();
  }, [syncScrollPosition]);

  useEffect(() => {
    if (keyboardHeight <= 0) return;
    scheduleTimeout(keyboardScrollTimerRef, 50, () => scrollToEndIfAtBottom(true));
  }, [keyboardHeight, scrollToEndIfAtBottom]);

  return {
    listRef,
    listBottomPadRef,
    newMessageCountRef,
    showScrollToBottom,
    scrollAwayCount,
    scrollToLatest,
    handleScroll,
    handleScrollEnd,
  };
}

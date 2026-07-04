import { useCallback, useEffect, useRef, useState } from "react";
import type { NativeScrollEvent, NativeSyntheticEvent } from "react-native";
import type { FlashListRef } from "@shopify/flash-list";

import { getStreamingDraftContentLength, subscribeStreamingDraft } from "@/lib/streamingDraftStore";
import type { Message } from "@/lib/api";
import { getScrollThresholds, resolveScrollAtBottom } from "@/lib/chatScrollLogic";
import { tap } from "@/lib/haptics";

const STREAMING_SCROLL_DEBOUNCE_MS = 150;

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
  const keyboardScrollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
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

  const scheduleStreamingScroll = useCallback(() => {
    if (streamingScrollTimerRef.current != null) {
      clearTimeout(streamingScrollTimerRef.current);
    }
    streamingScrollTimerRef.current = setTimeout(() => {
      streamingScrollTimerRef.current = null;
      if (atBottomRef.current) {
        listRef.current?.scrollToEnd({ animated: false });
      } else {
        requestAnimationFrame(() => syncScrollPosition());
      }
    }, STREAMING_SCROLL_DEBOUNCE_MS);
  }, [syncScrollPosition]);

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

  const prevStreamingLenRef = useRef(0);

  useEffect(() => {
    if (!streamActive) {
      const prev = prevStreamingLenRef.current;
      prevStreamingLenRef.current = 0;
      if (prev > 0 && atBottomRef.current) {
        requestAnimationFrame(() => {
          listRef.current?.scrollToEnd({ animated: false });
          requestAnimationFrame(() => {
            listRef.current?.scrollToEnd({ animated: false });
          });
        });
      }
      return;
    }

    const syncStreamingScroll = () => {
      const nextLen = getStreamingDraftContentLength();
      const prev = prevStreamingLenRef.current;
      prevStreamingLenRef.current = nextLen;

      if (nextLen > 0) {
        scheduleStreamingScroll();
      }
      if (prev > 0 && nextLen === 0 && atBottomRef.current) {
        requestAnimationFrame(() => {
          listRef.current?.scrollToEnd({ animated: false });
          requestAnimationFrame(() => {
            listRef.current?.scrollToEnd({ animated: false });
          });
        });
      }
    };

    syncStreamingScroll();
    return subscribeStreamingDraft(syncStreamingScroll);
  }, [streamActive, scheduleStreamingScroll]);

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
  }, [chatId]);

  useEffect(() => {
    return () => {
      if (streamingScrollTimerRef.current != null) {
        clearTimeout(streamingScrollTimerRef.current);
      }
      if (keyboardScrollTimerRef.current != null) {
        clearTimeout(keyboardScrollTimerRef.current);
      }
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
    if (keyboardScrollTimerRef.current != null) {
      clearTimeout(keyboardScrollTimerRef.current);
    }
    keyboardScrollTimerRef.current = setTimeout(() => {
      keyboardScrollTimerRef.current = null;
      scrollToEndIfAtBottom(true);
    }, 50);
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

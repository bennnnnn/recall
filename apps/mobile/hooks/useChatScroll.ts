import { useCallback, useEffect, useRef, useState } from "react";
import { Keyboard, Platform, type NativeScrollEvent, type NativeSyntheticEvent } from "react-native";
import type { FlashListRef } from "@shopify/flash-list";

import { tap } from "@/lib/haptics";
import type { Message } from "@/lib/api";
import { getScrollThresholds, resolveScrollAtBottom } from "@/lib/chatScrollLogic";

type Options = {
  chatId: string | null;
  messagesLength: number;
  streamingLen: number;
  windowHeight: number;
};

export function useChatScroll({
  chatId,
  messagesLength,
  streamingLen,
  windowHeight,
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
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);
  const [scrollAwayCount, setScrollAwayCount] = useState(0);
  const [keyboardHeight, setKeyboardHeight] = useState(0);

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
    if (streamingLen && atBottomRef.current) {
      listRef.current?.scrollToEnd({ animated: false });
    } else if (streamingLen) {
      requestAnimationFrame(() => syncScrollPosition());
    }
  }, [streamingLen, syncScrollPosition]);

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
    const showEvent = Platform.OS === "ios" ? "keyboardWillShow" : "keyboardDidShow";
    const hideEvent = Platform.OS === "ios" ? "keyboardWillHide" : "keyboardDidHide";

    const show = Keyboard.addListener(showEvent, (e) => {
      setKeyboardHeight(Math.max(0, windowHeight - e.endCoordinates.screenY));
      setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 50);
    });
    const hide = Keyboard.addListener(hideEvent, () => setKeyboardHeight(0));
    return () => {
      show.remove();
      hide.remove();
    };
  }, [windowHeight]);

  return {
    listRef,
    listBottomPadRef,
    newMessageCountRef,
    showScrollToBottom,
    scrollAwayCount,
    keyboardHeight,
    scrollToLatest,
    handleScroll,
    handleScrollEnd,
  };
}

import React from "react";
import { Text } from "react-native";
import { renderHook } from "@testing-library/react-native";

import { useChatScreenBodyProps } from "@/hooks/useChatScreenBodyProps";
import type { Message } from "@/lib/api";
import { lightTheme } from "@/lib/theme";

jest.mock("@/components/chat/ChatHeader", () => ({
  ChatHeader: () => null,
}));

jest.mock("@/lib/drawer", () => ({
  openDrawer: jest.fn(),
}));

const message: Message = {
  id: "message-1",
  role: "assistant",
  content: "Hello",
  model: "free-chat",
  created_at: "2026-09-19T00:00:00Z",
};

const renderItem = jest.fn(({ item }: { item: Message }) => <Text>{item.content}</Text>);
const loadOlderMessages = jest.fn(async () => undefined);
const handleScroll = jest.fn();
const handleScrollEnd = jest.fn();
const handleSend = jest.fn();
const scrollToLatest = jest.fn();
const dismissActionBanner = jest.fn();
const startNewChat = jest.fn();
const setMenuVisible = jest.fn();
const closeAttachSheet = jest.fn();
const setPendingAttachment = jest.fn();
const handlePickAttachment = jest.fn();
const handleAttachmentSheetSelect = jest.fn(async () => undefined);
const closeMathScanner = jest.fn();
const handleMathScanCaptured = jest.fn();
const readMathScan = jest.fn(async () => null);
const handleMathScanSolve = jest.fn();
const quotaDismiss = jest.fn();
const retryChatError = jest.fn();
const dismissChatError = jest.fn();
const stopGeneration = jest.fn();
const toggleVoiceInput = jest.fn(async () => undefined);
const handleHeaderHeightChange = jest.fn();
const styles = {} as never;
const listRef = { current: null };
const listBottomPadRef = { current: 0 };

const router = {
  setParams: jest.fn(),
  push: jest.fn(),
} as never;

function useHarness(streaming: boolean, messages: Message[], drawerOpen = false) {
  return useChatScreenBodyProps({
    styles,
    theme: lightTheme,
    drawerOpen,
    routeChatId: "chat-1",
    layout: {
      headerMinimumHeight: 72,
      headerInset: 72,
      onHeaderHeightChange: handleHeaderHeightChange,
      composerClearance: 96,
      listBottomPad: 104,
      emptyHeight: 500,
    },
    listBottomPadRef,
    actionBanner: null,
    dismissActionBanner,
    header: {
      insetsTop: 24,
      router,
      headerTitleLabel: "Trip",
      titleGenerating: false,
      chatTitle: "Trip",
      startNewChat,
      setMenuVisible,
      menuOverlayOpen: false,
    },
    list: {
      listRef,
      messages,
      hasMoreOlder: false,
      loadingOlder: false,
      chatLoading: false,
      renderItem,
      loadOlderMessages,
      handleScroll,
      handleScrollEnd,
    },
    handleSend,
    showScrollToBottom: false,
    scrollAwayCount: 0,
    scrollToLatest,
    attachments: {
      attachSheetOpen: false,
      closeAttachSheet,
      attachBusy: false,
      attachPicking: false,
      pendingAttachment: null,
      setPendingAttachment,
      handlePickAttachment,
      handleAttachmentSheetSelect,
      mathScannerOpen: false,
      closeMathScanner,
      handleMathScanCaptured,
      readMathScan,
      handleMathScanSolve,
    },
    quotaNudge: {
      show: false,
      usedPct: 0,
      dismiss: quotaDismiss,
    },
    chatError: null,
    isPro: false,
    retryChatError,
    dismissChatError,
    streaming,
    sendBusy: false,
    stopGeneration,
    isOffline: false,
    voice: {
      voiceAvailable: true,
      voiceRecording: false,
      voiceTranscribing: false,
      voiceMeterLevel: 0.12,
      toggleVoiceInput,
    },
  });
}

describe("useChatScreenBodyProps", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("keeps unaffected groups and FlashList callbacks stable while streaming changes", async () => {
    const firstMessages = [message];
    const { result, rerender } = await renderHook(
      ({ streaming, messages }) => useHarness(streaming, messages),
      { initialProps: { streaming: false, messages: firstMessages } },
    );
    const initial = result.current.bodyProps;
    const initialListCallbacks = {
      renderItem: initial.list.renderItem,
      onLoadOlder: initial.list.onLoadOlder,
      onScroll: initial.list.onScroll,
      onScrollEnd: initial.list.onScrollEnd,
      onSelectStarter: initial.list.onSelectStarter,
    };

    await rerender({ streaming: true, messages: firstMessages });
    const streaming = result.current.bodyProps;

    expect(streaming.layout).toBe(initial.layout);
    expect(streaming.list).toBe(initial.list);
    expect(streaming.chrome).toBe(initial.chrome);
    expect(streaming.sheets).toBe(initial.sheets);
    expect(streaming.composer).not.toBe(initial.composer);
    expect(streaming.composer.streaming).toBe(true);
    expect({
      renderItem: streaming.list.renderItem,
      onLoadOlder: streaming.list.onLoadOlder,
      onScroll: streaming.list.onScroll,
      onScrollEnd: streaming.list.onScrollEnd,
      onSelectStarter: streaming.list.onSelectStarter,
    }).toEqual(initialListCallbacks);

    await rerender({ streaming: true, messages: firstMessages });
    expect(result.current.bodyProps).toBe(streaming);
  });

  it("updates only the list group when the message collection changes", async () => {
    const firstMessages = [message];
    const { result, rerender } = await renderHook(
      ({ messages }) => useHarness(false, messages),
      { initialProps: { messages: firstMessages } },
    );
    const initial = result.current.bodyProps;
    const nextMessages = [
      ...firstMessages,
      { ...message, id: "message-2", content: "Streaming token" },
    ];

    await rerender({ messages: nextMessages });
    const updated = result.current.bodyProps;

    expect(updated.layout).toBe(initial.layout);
    expect(updated.list).not.toBe(initial.list);
    expect(updated.list.messages).toBe(nextMessages);
    expect(updated.list.renderItem).toBe(initial.list.renderItem);
    expect(updated.composer).toBe(initial.composer);
    expect(updated.chrome).toBe(initial.chrome);
    expect(updated.sheets).toBe(initial.sheets);
  });

  it("hides header chrome while the drawer is open without dropping the measured list inset", async () => {
    const { result } = await renderHook(() => useHarness(false, [message], true));

    expect(result.current.bodyProps.list.header).toBeNull();
    expect(result.current.bodyProps.layout.headerInset).toBe(72);
  });
});

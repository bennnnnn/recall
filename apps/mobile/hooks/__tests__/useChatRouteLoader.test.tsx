import React from "react";
import { Text } from "react-native";
import { act, render, waitFor } from "@testing-library/react-native";

import { useChatRouteLoader } from "@/hooks/useChatRouteLoader";

jest.mock("expo-router", () => ({
  useFocusEffect: () => undefined,
  useRouter: () => ({}),
}));
jest.mock("@/lib/api", () => ({
  api: {
    getChat: jest.fn(),
    listMessages: jest.fn(),
  },
}));
jest.mock("@/lib/cache/chatListCache", () => ({
  getCachedChat: jest.fn(() => undefined),
}));
jest.mock("@/lib/chatMessageCache", () => ({
  readCachedChatMessages: jest.fn(async () => null),
  writeCachedChatMessages: jest.fn(async () => undefined),
  cachedChatPageFetchedAt: (cached: { cached_at?: string } | null) => {
    if (!cached?.cached_at) return undefined;
    const at = Date.parse(cached.cached_at);
    return Number.isFinite(at) ? at : undefined;
  },
}));
jest.mock("@/hooks/useChatTitlePolling", () => ({
  useChatTitlePolling: () => ({
    titleGenerating: false,
    pollForTitle: jest.fn(),
    handleFirstReply: mockHandleFirstReply,
  }),
}));
jest.mock("@/hooks/useChatHighlightScroll", () => ({
  useChatHighlightScroll: () => ({ highlightedMessageId: null }),
}));

import { api } from "@/lib/api";
import { getCachedChat } from "@/lib/cache/chatListCache";
import { readCachedChatMessages } from "@/lib/chatMessageCache";

const mockHandleFirstReply = jest.fn();
const setChatId = jest.fn();
const setMessages = jest.fn();
const setQuizVariant = jest.fn();

function Probe() {
  const result = useChatRouteLoader({
    token: "token",
    routeChatId: "chat-1",
    routeHighlightMessage: undefined,
    router: { setParams: jest.fn() } as never,
    draft: {
      draftChatIdRef: { current: null },
      draftProjectIdRef: { current: null },
      draftQuizModeRef: { current: null },
      skipLoadForChatIdRef: { current: null },
      creatingRef: { current: false },
      discardEmptyChat: jest.fn(),
      clearDraftChat: jest.fn(),
      prepareDraftChat: jest.fn(),
    } as never,
    chatId: null,
    setChatId,
    setMessages,
    messages: [],
    streaming: false,
    stopGeneration: jest.fn(),
    setQuizVariant,
    resolveQuizVariant: () => "vocab",
    listRef: { current: null },
    showActionBanner: jest.fn(),
    t: (key) => key,
  });
  return <Text>{result.chatLoading ? "loading" : "ready"}</Text>;
}

describe("useChatRouteLoader", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (getCachedChat as jest.Mock).mockReturnValue(undefined);
    (readCachedChatMessages as jest.Mock).mockResolvedValue(null);
    (api.getChat as jest.Mock).mockResolvedValue({
      id: "chat-1",
      title: "Loaded",
      pinned: true,
      archived: false,
      project_id: "project-1",
    });
    (api.listMessages as jest.Mock).mockResolvedValue({
      messages: [{ id: "m1", role: "assistant", content: "Hello" }],
      has_more: false,
    });
  });

  it("skips GET /chats/{id} when the drawer list already has the row", async () => {
    (getCachedChat as jest.Mock).mockReturnValue({
      id: "chat-1",
      title: "From drawer",
      pinned: false,
      archived: false,
      project_id: null,
    });
    await act(async () => {
      render(<Probe />);
    });
    await waitFor(() => {
      expect(api.listMessages).toHaveBeenCalledWith("token", "chat-1", { limit: 40 });
    });
    expect(api.getChat).not.toHaveBeenCalled();
  });

  it("skips network when the drawer row and a message cache exist", async () => {
    (getCachedChat as jest.Mock).mockReturnValue({
      id: "chat-1",
      title: "From drawer",
      pinned: false,
      archived: false,
      project_id: null,
    });
    (readCachedChatMessages as jest.Mock).mockResolvedValue({
      messages: [{ id: "m1", role: "assistant", content: "Hello" }],
      has_more: false,
      cached_at: new Date(Date.now() - 60_000).toISOString(),
    });
    await act(async () => {
      render(<Probe />);
    });
    await waitFor(() => {
      expect(setChatId).toHaveBeenCalledWith("chat-1");
    });
    expect(api.getChat).not.toHaveBeenCalled();
    expect(api.listMessages).not.toHaveBeenCalled();
  });

  it("loads chat metadata and messages together for the route", async () => {
    await act(async () => {
      render(<Probe />);
    });

    await waitFor(() => {
      expect(api.getChat).toHaveBeenCalledWith("token", "chat-1");
      expect(api.listMessages).toHaveBeenCalledWith("token", "chat-1", { limit: 40 });
      expect(setChatId).toHaveBeenCalledWith("chat-1");
      expect(setQuizVariant).toHaveBeenCalledWith("vocab");
    });
  });

  it("leaves an in-flight turn running when New chat is tapped", async () => {
    const stopGeneration = jest.fn();
    const setParams = jest.fn();
    let startNewChat: ((opts?: { force?: boolean }) => void) | undefined;
    function StreamingProbe() {
      const result = useChatRouteLoader({
        token: "token",
        routeChatId: "open-1",
        routeHighlightMessage: undefined,
        router: { setParams } as never,
        draft: {
          draftChatIdRef: { current: null },
          draftProjectIdRef: { current: null },
          draftQuizModeRef: { current: null },
          skipLoadForChatIdRef: { current: "open-1" },
          creatingRef: { current: false },
          discardEmptyChat: jest.fn(),
          clearDraftChat: jest.fn(),
          prepareDraftChat: jest.fn(),
        } as never,
        chatId: "open-1",
        setChatId,
        setMessages,
        messages: [
          {
            id: "u1",
            role: "user",
            content: "Tell me a long story",
            model: null,
            created_at: "t",
          },
          {
            id: "streaming",
            role: "assistant",
            content: "Once upon",
            model: null,
            created_at: "t",
          },
        ],
        streaming: true,
        stopGeneration,
        setQuizVariant,
        resolveQuizVariant: () => "vocab",
        listRef: { current: null },
        showActionBanner: jest.fn(),
        t: (key) => key,
      });
      startNewChat = result.startNewChat;
      return <Text>ready</Text>;
    }
    await act(async () => {
      render(<StreamingProbe />);
    });
    await act(async () => {
      startNewChat?.();
    });
    expect(stopGeneration).not.toHaveBeenCalled();
    expect(mockHandleFirstReply).toHaveBeenCalled();
    expect(setChatId).toHaveBeenCalledWith(null);
    expect(setMessages).toHaveBeenCalledWith([]);
    expect(setParams).toHaveBeenCalledWith({ chatId: undefined });
  });

  it("stops an in-flight turn when New chat is forced (deleted chat)", async () => {
    const stopGeneration = jest.fn();
    let startNewChat: ((opts?: { force?: boolean }) => void) | undefined;
    function DeletedProbe() {
      const result = useChatRouteLoader({
        token: "token",
        routeChatId: "open-1",
        routeHighlightMessage: undefined,
        router: { setParams: jest.fn() } as never,
        draft: {
          draftChatIdRef: { current: null },
          draftProjectIdRef: { current: null },
          draftQuizModeRef: { current: null },
          skipLoadForChatIdRef: { current: "open-1" },
          creatingRef: { current: false },
          discardEmptyChat: jest.fn(),
          clearDraftChat: jest.fn(),
          prepareDraftChat: jest.fn(),
        } as never,
        chatId: "open-1",
        setChatId,
        setMessages,
        messages: [
          {
            id: "u1",
            role: "user",
            content: "hi",
            model: null,
            created_at: "t",
          },
        ],
        streaming: true,
        stopGeneration,
        setQuizVariant,
        resolveQuizVariant: () => "vocab",
        listRef: { current: null },
        showActionBanner: jest.fn(),
        t: (key) => key,
      });
      startNewChat = result.startNewChat;
      return <Text>ready</Text>;
    }
    await act(async () => {
      render(<DeletedProbe />);
    });
    await act(async () => {
      startNewChat?.({ force: true });
    });
    expect(stopGeneration).toHaveBeenCalled();
  });
});

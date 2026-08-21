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
jest.mock("@/lib/chatMessageCache", () => ({
  readCachedChatMessages: jest.fn(async () => null),
  writeCachedChatMessages: jest.fn(async () => undefined),
}));
jest.mock("@/hooks/useChatTitlePolling", () => ({
  useChatTitlePolling: () => ({
    titleGenerating: false,
    pollForTitle: jest.fn(),
    handleFirstReply: jest.fn(),
  }),
}));
jest.mock("@/hooks/useChatHighlightScroll", () => ({
  useChatHighlightScroll: () => ({ highlightedMessageId: null }),
}));

import { api } from "@/lib/api";

const setChatId = jest.fn();
const setMessages = jest.fn();
const setQuizVariant = jest.fn();

function Probe() {
  const result = useChatRouteLoader({
    token: "token",
    routeChatId: "chat-1",
    routeHighlightMessage: undefined,
    routePrompt: undefined,
    routeLaunchId: undefined,
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
    setQuizLanguage: jest.fn(),
    setQuizVariant,
    resolveQuizVariant: () => "vocab",
    setInputRef: { current: jest.fn() },
    listRef: { current: null },
    showActionBanner: jest.fn(),
    t: (key) => key,
  });
  return <Text>{result.chatLoading ? "loading" : "ready"}</Text>;
}

describe("useChatRouteLoader", () => {
  beforeEach(() => {
    jest.clearAllMocks();
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
});

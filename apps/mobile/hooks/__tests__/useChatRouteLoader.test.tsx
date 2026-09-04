import React, { useLayoutEffect, useState } from "react";
import { Text } from "react-native";
import { act, render, waitFor } from "@testing-library/react-native";

import { useChatRouteLoader } from "@/hooks/useChatRouteLoader";
import { api, type Message } from "@/lib/api";
import { getCachedChat } from "@/lib/cache/chatListCache";
import { clearCachedChatMessages, readCachedChatMessages, writeCachedChatMessages } from "@/lib/chatMessageCache";


let mockSession = 0;
let mockRevision = 0;
let mockChatChange: ((id: string, patch: Record<string, unknown> | null) => void) | undefined;
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));
jest.mock("@/lib/drawer", () => ({
  getChatMutationRevision: () => mockRevision,
  subscribeChatChanges: (fn: typeof mockChatChange) => { mockChatChange = fn; return () => { mockChatChange = undefined; }; },
  removeChatGlobal: jest.fn(),
}));
jest.mock("@/lib/api/client", () => ({
  ApiRequestError: class extends Error { status: number; constructor(status: number) { super("Request failed"); this.status = status; } },
}));
import { ApiRequestError } from "@/lib/api/client";

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
  clearCachedChatMessages: jest.fn(async () => undefined),
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
    mockSession = 0;
    mockRevision = 0;
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

  it("revalidates a cached transcript when reopening a chat", async () => {
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
    expect(api.listMessages).toHaveBeenCalledWith("token", "chat-1", { limit: 40 });
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
      useLayoutEffect(() => { startNewChat = result.startNewChat; });
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
      useLayoutEffect(() => { startNewChat = result.startNewChat; });
      return <Text>ready</Text>;
    }
    await act(async () => {
      render(<DeletedProbe />);
    });
    await act(async () => {
      startNewChat?.({ force: true });
    });
    expect(stopGeneration).toHaveBeenCalled();
    expect(mockHandleFirstReply).not.toHaveBeenCalled();
  });
});


function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

const message = (id: string, content: string): Message => ({
  id, content, role: "assistant", model: null, created_at: "2026-01-01T00:00:00Z",
});
let routeState: ReturnType<typeof useChatRouteLoader>;
let visibleMessages: Message[];
const routeDraft = {
  draftChatIdRef: { current: null },
  draftProjectIdRef: { current: null },
  skipLoadForChatIdRef: { current: null },
  creatingRef: { current: false },
  discardEmptyChat: jest.fn(),
  clearDraftChat: jest.fn(),
};
const resolveVariant = () => "vocab" as const;
const banner = jest.fn();
const translate = (key: string) => key;
function RouteProbe({ routeId, token = "token" }: { routeId: string; token?: string }) {
  const [chatId, updateChatId] = useState<string | null>(null);
  const [messages, updateMessages] = useState<Message[]>([]);
  const result = useChatRouteLoader({
    token, routeChatId: routeId, routeHighlightMessage: undefined,
    router: { setParams: jest.fn() } as never,
    draft: routeDraft as never,
    chatId, setChatId: updateChatId, messages, setMessages: updateMessages,
    streaming: false, stopGeneration: jest.fn(), setQuizVariant,
    resolveQuizVariant: resolveVariant, listRef: { current: null },
    showActionBanner: banner, t: translate,
  });
  useLayoutEffect(() => { routeState = result; visibleMessages = messages; });
  return <Text>{result.chatLoading ? "loading" : "ready"}</Text>;
}

describe("chat history navigation races", () => {
  const current = message("11111111-1111-1111-1111-111111111111", "A current");
  beforeEach(() => {
    jest.clearAllMocks();
    mockSession = 0;
    mockRevision = 0;
    (getCachedChat as jest.Mock).mockReturnValue(undefined);
    (readCachedChatMessages as jest.Mock).mockResolvedValue(null);
    (api.getChat as jest.Mock).mockImplementation(async (_token, id) => ({
      id, title: id, pinned: false, archived: false, project_id: null,
    }));
    (api.listMessages as jest.Mock).mockResolvedValue({ messages: [current], has_more: true });
  });

  it.each([false, true])("ignores older pages after navigation (return to A: %s)", async (returnToA) => {
    const page = deferred<{ messages: Message[]; has_more: boolean }>();
    const view = await render(<RouteProbe routeId="chat-a" />);
    await waitFor(() => expect(routeState.chatLoading).toBe(false));
    (api.listMessages as jest.Mock).mockReturnValueOnce(page.promise);
    let loading!: Promise<void>;
    await act(async () => { loading = routeState.loadOlderMessages(); });
    const other = message("22222222-2222-2222-2222-222222222222", "Current route only");
    (api.listMessages as jest.Mock).mockResolvedValue({ messages: [other], has_more: false });
    await view.rerender(<RouteProbe routeId="chat-b" />);
    await waitFor(() => expect(visibleMessages).toEqual([other]));
    if (returnToA) {
      await view.rerender(<RouteProbe routeId="chat-a" />);
      await waitFor(() => expect(routeState.chatLoading).toBe(false));
    }
    await act(async () => {
      page.resolve({ messages: [message("old-a", "A older")], has_more: true });
      await loading;
    });
    expect(visibleMessages).toEqual([other]);
    expect(routeState.hasMoreOlder).toBe(false);
  });

  it("rejects a retained pagination callback from a previous route", async () => {
    const view = await render(<RouteProbe routeId="chat-a" />);
    await waitFor(() => expect(routeState.chatLoading).toBe(false));
    const loadA = routeState.loadOlderMessages;
    await view.rerender(<RouteProbe routeId="chat-b" />);
    await waitFor(() => expect(routeState.chatLoading).toBe(false));
    (api.listMessages as jest.Mock).mockClear();
    await act(async () => { await loadA(); });
    expect(api.listMessages).not.toHaveBeenCalled();
  });

  it("requests a history page only once for rapid repeated scroll events", async () => {
    const page = deferred<{ messages: Message[]; has_more: boolean }>();
    await render(<RouteProbe routeId="chat-a" />);
    await waitFor(() => expect(routeState.chatLoading).toBe(false));
    (api.listMessages as jest.Mock).mockClear().mockReturnValue(page.promise);
    let first!: Promise<void>;
    let second!: Promise<void>;
    await act(async () => {
      first = routeState.loadOlderMessages();
      second = routeState.loadOlderMessages();
    });
    expect(api.listMessages).toHaveBeenCalledTimes(1);
    await act(async () => {
      page.resolve({ messages: [message("old-a", "A older")], has_more: false });
      await Promise.all([first, second]);
    });
    expect(visibleMessages.map((m) => m.content)).toEqual(["A older", "A current"]);
  });

  it("shows cached history immediately and replaces it with the saved latest turn", async () => {
    const page = deferred<{ messages: Message[]; has_more: boolean }>();
    (readCachedChatMessages as jest.Mock).mockResolvedValue({
      messages: [current], has_more: false, cached_at: new Date().toISOString(),
    });
    (api.listMessages as jest.Mock).mockReturnValue(page.promise);
    await render(<RouteProbe routeId="chat-a" />);
    expect(visibleMessages).toEqual([current]);
    const reply = message("new-reply", "Latest saved answer");
    await act(async () => {
      page.resolve({ messages: [current, reply], has_more: false });
    });
    expect(visibleMessages).toEqual([current, reply]);
    expect(routeState.chatLoading).toBe(false);
  });

  it("preserves the loaded conversation across an access-token refresh", async () => {
    const view = await render(<RouteProbe routeId="chat-a" />);
    await waitFor(() => expect(routeState.chatLoading).toBe(false));
    (api.listMessages as jest.Mock).mockClear();
    (readCachedChatMessages as jest.Mock).mockClear();
    await view.rerender(<RouteProbe routeId="chat-a" token="refreshed" />);
    expect(visibleMessages).toEqual([current]);
    expect(api.listMessages).not.toHaveBeenCalled();
    expect(readCachedChatMessages).not.toHaveBeenCalled();
  });

  it("ignores a history response immediately after logout, before React rerenders", async () => {
    const page = deferred<{ messages: Message[]; has_more: boolean }>();
    (api.listMessages as jest.Mock).mockReturnValue(page.promise);
    await render(<RouteProbe routeId="chat-a" />);
    mockSession++;
    await act(async () => { page.resolve({ messages: [current], has_more: false }); });
    expect(visibleMessages).toEqual([]);
    expect(writeCachedChatMessages).not.toHaveBeenCalled();
  });

  it("applies drawer metadata immediately and keeps it when an older load completes", async () => {
    const page = deferred<{ messages: Message[]; has_more: boolean }>();
    (api.listMessages as jest.Mock).mockReturnValue(page.promise);
    await render(<RouteProbe routeId="chat-a" />);
    const updated = { id: "chat-a", title: "Manual title", pinned: true, archived: false, project_id: null };
    await act(async () => {
      mockRevision++;
      (getCachedChat as jest.Mock).mockReturnValue(updated);
      mockChatChange?.("chat-a", updated);
    });
    expect(routeState.chatTitle).toBe("Manual title");
    expect(routeState.pinned).toBe(true);
    await act(async () => { page.resolve({ messages: [current], has_more: false }); });
    expect(routeState.chatTitle).toBe("Manual title");
    expect(routeState.pinned).toBe(true);
    expect(visibleMessages).toEqual([current]);
  });

  it("cannot restore a deleted conversation before route params rerender", async () => {
    const page = deferred<{ messages: Message[]; has_more: boolean }>();
    (api.listMessages as jest.Mock).mockReturnValue(page.promise);
    await render(<RouteProbe routeId="chat-a" />);
    await act(async () => { routeState.startNewChat({ force: true }); });
    await act(async () => { page.resolve({ messages: [current], has_more: false }); });
    expect(visibleMessages).toEqual([]);
    expect(routeState.chatTitle).toBeNull();
    expect(writeCachedChatMessages).not.toHaveBeenCalled();
  });

  it("clears cached history when the server confirms the chat is gone", async () => {
    (readCachedChatMessages as jest.Mock).mockResolvedValue({ messages: [current], has_more: true });
    (api.listMessages as jest.Mock).mockRejectedValue(new ApiRequestError(404, "Gone"));
    await render(<RouteProbe routeId="chat-a" />);
    await waitFor(() => expect(routeState.chatLoading).toBe(false));
    expect(visibleMessages).toEqual([]);
    expect(clearCachedChatMessages).toHaveBeenCalledWith("chat-a");
  });

  it("keeps cached history during a temporary service failure", async () => {
    (readCachedChatMessages as jest.Mock).mockResolvedValue({ messages: [current], has_more: true });
    (api.listMessages as jest.Mock).mockRejectedValue(new ApiRequestError(503, "Unavailable"));
    await render(<RouteProbe routeId="chat-a" />);
    await waitFor(() => expect(routeState.chatLoading).toBe(false));
    expect(visibleMessages).toEqual([current]);
    expect(clearCachedChatMessages).not.toHaveBeenCalled();
  });

});

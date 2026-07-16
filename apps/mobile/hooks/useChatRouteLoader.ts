import { useCallback, useEffect, useRef, useState } from "react";
import { AppState, type AppStateStatus } from "react-native";
import type { FlashListRef } from "@shopify/flash-list";
import { useFocusEffect, useRouter } from "expo-router";
import type { Ionicons } from "@expo/vector-icons";

type Router = ReturnType<typeof useRouter>;

import { api, type Message } from "@/lib/api";
import { readCachedChatMessages, writeCachedChatMessages } from "@/lib/chatMessageCache";
import { MESSAGE_PAGE_SIZE } from "@/lib/chatConstants";
import type { QueuedChatLaunch } from "@/lib/chatLaunch";
import { takeQueuedChatLaunch } from "@/lib/chatLaunch";
import type { QuizVariant } from "@/lib/quizVariant";
import type { useDraftChat } from "@/hooks/useDraftChat";
import { useChatHighlightScroll } from "@/hooks/useChatHighlightScroll";
import { useChatTitlePolling } from "@/hooks/useChatTitlePolling";

type DraftChat = ReturnType<typeof useDraftChat>;

type Options = {
  token: string | null;
  routeChatId: string | undefined;
  routeHighlightMessage: string | undefined;
  routePrompt: string | undefined;
  routeLaunchId: string | undefined;
  router: Router;
  draft: DraftChat;
  chatId: string | null;
  setChatId: React.Dispatch<React.SetStateAction<string | null>>;
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  messages: Message[];
  streaming: boolean;
  stopGeneration: () => void;
  setQuizLanguage: React.Dispatch<React.SetStateAction<string>>;
  setQuizVariant: React.Dispatch<React.SetStateAction<QuizVariant>>;
  resolveQuizVariant: (projectId: string | null | undefined) => QuizVariant;
  setInputRef: React.MutableRefObject<(value: string) => void>;
  listRef: React.RefObject<FlashListRef<Message> | null>;
  showActionBanner: (message: string, icon?: keyof typeof Ionicons.glyphMap) => void;
  t: (key: string) => string;
  onFocusLaunch?: () => void;
};

export function useChatRouteLoader({
  token,
  routeChatId,
  routeHighlightMessage,
  routePrompt,
  routeLaunchId,
  router,
  draft,
  chatId,
  setChatId,
  setMessages,
  messages,
  streaming,
  stopGeneration,
  setQuizLanguage,
  setQuizVariant,
  resolveQuizVariant,
  setInputRef,
  listRef,
  showActionBanner,
  t,
}: Options) {
  const {
    draftChatIdRef,
    draftProjectIdRef,
    draftQuizModeRef,
    skipLoadForChatIdRef,
    creatingRef,
    discardEmptyChat,
    clearDraftChat,
    prepareDraftChat,
  } = draft;

  const [chatTitle, setChatTitle] = useState<string | null>(null);
  const { titleGenerating, pollForTitle, handleFirstReply } = useChatTitlePolling({
    token,
    chatId,
    setChatTitle,
  });
  const [pinned, setPinned] = useState(false);
  const [archived, setArchived] = useState(false);
  const [chatLoading, setChatLoading] = useState(false);
  const [hasMoreOlder, setHasMoreOlder] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [pendingLaunch, setPendingLaunch] = useState<string | null>(null);

  const priorRouteChatIdRef = useRef<string | null>(null);
  const pendingLaunchRef = useRef<string | null>(null);
  const pendingProjectIdRef = useRef<string | null>(null);
  const pendingQuizModeRef = useRef<import("@/lib/quizMode").QuizMode | null>(null);
  const handledLaunchIdRef = useRef<string | null>(null);
  const skipNextFocusRef = useRef(true);

  useEffect(() => {
    const onAppState = (state: AppStateStatus) => {
      if (state !== "background" && state !== "inactive") return;
      const draftId = draftChatIdRef.current;
      if (!draftId) return;
      // Empty pre-created drafts should not survive backgrounding.
      if (messages.length === 0 && chatId == null) {
        discardEmptyChat(draftId);
        clearDraftChat();
      }
    };
    const sub = AppState.addEventListener("change", onAppState);
    return () => sub.remove();
  }, [messages.length, chatId, discardEmptyChat, clearDraftChat, draftChatIdRef]);

  useEffect(() => {
    skipNextFocusRef.current = true;
  }, [routeChatId]);

  useEffect(() => {
    if (!token) {
      setChatLoading(false);
      return;
    }
    const openChatId = typeof routeChatId === "string" ? routeChatId : null;
    const prevOpenChatId = priorRouteChatIdRef.current;
    if (prevOpenChatId && prevOpenChatId !== openChatId) {
      discardEmptyChat(prevOpenChatId);
    }
    if (openChatId && draftChatIdRef.current) {
      clearDraftChat();
    }
    priorRouteChatIdRef.current = openChatId;

    let cancelled = false;
    (async () => {
      if (!openChatId) {
        setChatLoading(false);
        if (!creatingRef.current) {
          setChatId(null);
          setChatTitle(null);
          setPinned(false);
          setArchived(false);
          setMessages([]);
          setHasMoreOlder(false);
        }
        return;
      }
      if (skipLoadForChatIdRef.current === openChatId) {
        skipLoadForChatIdRef.current = null;
        setChatId(openChatId);
        setChatLoading(false);
        return;
      }
      setChatLoading(true);
      setHasMoreOlder(false);
      try {
        const cached = await readCachedChatMessages(openChatId);
        if (cancelled) return;
        if (cached) {
          setChatId(openChatId);
          setMessages(cached.messages);
          setHasMoreOlder(cached.has_more);
          setChatLoading(false);
        }
        const [chat, page] = await Promise.all([
          api.getChat(token, openChatId),
          api.listMessages(token, openChatId, { limit: MESSAGE_PAGE_SIZE }),
        ]);
        if (cancelled) return;
        setChatId(chat.id);
        setChatTitle(chat.title);
        setPinned(chat.pinned);
        setArchived(Boolean(chat.archived));
        draftProjectIdRef.current = chat.project_id ?? draftProjectIdRef.current;
        setQuizVariant(resolveQuizVariant(chat.project_id));
        setMessages(page.messages);
        setHasMoreOlder(page.has_more);
        void writeCachedChatMessages(openChatId, page.messages, page.has_more);
        if (!chat.title && page.messages.length > 0) {
          pollForTitle(token, openChatId);
        }
      } catch {
        if (!cancelled) {
          showActionBanner(t("common.error"), "alert-circle-outline");
        }
      } finally {
        if (!cancelled) setChatLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, routeChatId]);

  useFocusEffect(
    useCallback(() => {
      const openChatId = typeof routeChatId === "string" ? routeChatId : null;
      if (skipNextFocusRef.current) {
        skipNextFocusRef.current = false;
        return;
      }
      if (!token || !openChatId || streaming || chatLoading) return;

      // Cancel in-flight refetch if the screen blurs or deps change (e.g. the
      // user navigates to a different chat mid-fetch). Without this, a slow
      // refetch for chat A could land after we've switched to chat B and
      // overwrite B's messages with A's.
      let cancelled = false;
      void (async () => {
        try {
          const [chat, page] = await Promise.all([
            api.getChat(token, openChatId),
            api.listMessages(token, openChatId, { limit: MESSAGE_PAGE_SIZE }),
          ]);
          if (cancelled) return;
          setChatId(chat.id);
          setChatTitle(chat.title);
          setPinned(chat.pinned);
          setArchived(Boolean(chat.archived));
          draftProjectIdRef.current = chat.project_id ?? draftProjectIdRef.current;
          setQuizVariant(resolveQuizVariant(chat.project_id));
          setMessages(page.messages);
          setHasMoreOlder(page.has_more);
          void writeCachedChatMessages(openChatId, page.messages, page.has_more);
        } catch {
          /* keep existing messages on silent refetch failure */
        }
      })();
      return () => {
        cancelled = true;
      };
    }, [token, routeChatId, streaming, chatLoading, setChatId, setMessages]),
  );

  const loadOlderMessages = useCallback(async () => {
    if (!token || !chatId || loadingOlder || !hasMoreOlder || messages.length === 0) return;
    const oldest = messages[0];
    const isServerId =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(oldest.id);
    if (!isServerId) return;

    setLoadingOlder(true);
    try {
      const page = await api.listMessages(token, chatId, {
        limit: MESSAGE_PAGE_SIZE,
        before: oldest.id,
      });
      setMessages((prev) => [...page.messages, ...prev]);
      setHasMoreOlder(page.has_more);
    } catch {
      showActionBanner(t("common.error"), "cloud-offline-outline");
    } finally {
      setLoadingOlder(false);
    }
  }, [token, chatId, loadingOlder, hasMoreOlder, messages, setMessages, showActionBanner, t]);

  const { highlightedMessageId } = useChatHighlightScroll({
    routeHighlightMessage,
    router,
    messages,
    hasMoreOlder,
    loadingOlder,
    token,
    chatId,
    loadOlderMessages,
    listRef,
  });

  const startNewChat = useCallback(
    (opts?: { force?: boolean }) => {
      if (streaming) {
        if (!opts?.force) return;
        stopGeneration();
      }
      discardEmptyChat(chatId);
      clearDraftChat();
      pendingProjectIdRef.current = null;
      setInputRef.current("");
      setChatId(null);
      setChatTitle(null);
      setPinned(false);
      setArchived(false);
      setMessages([]);
      setHasMoreOlder(false);
      if (routeChatId != null) {
        router.setParams({ chatId: undefined });
      }
      void prepareDraftChat();
    },
    [
      streaming,
      stopGeneration,
      chatId,
      discardEmptyChat,
      clearDraftChat,
      routeChatId,
      router,
      setMessages,
      setInputRef,
      prepareDraftChat,
      setChatId,
    ],
  );

  const beginChatLaunch = useCallback(
    (launch: QueuedChatLaunch | string) => {
      const queued = typeof launch === "string" ? { prompt: launch.trim() } : launch;
      const prompt = queued.prompt?.trim() ?? "";
      if (!prompt) return;
      if (streaming) stopGeneration();
      discardEmptyChat(chatId);
      clearDraftChat();
      draftProjectIdRef.current = queued.projectId ?? null;
      pendingProjectIdRef.current = queued.projectId ?? null;
      draftQuizModeRef.current = queued.quizMode ?? null;
      pendingQuizModeRef.current = queued.quizMode ?? null;
      setQuizLanguage(queued.quizLanguage ?? "en");
      setQuizVariant(queued.quizVariant ?? resolveQuizVariant(queued.projectId));
      setInputRef.current("");
      setChatId(null);
      setChatTitle(null);
      setPinned(false);
      setArchived(false);
      setMessages([]);
      setHasMoreOlder(false);
      creatingRef.current = false;
      if (routeChatId != null) {
        router.setParams({ chatId: undefined });
      }
      pendingLaunchRef.current = prompt;
      setPendingLaunch(prompt);
      void prepareDraftChat(queued.projectId, "auto", queued.quizMode);
    },
    [
      streaming,
      stopGeneration,
      discardEmptyChat,
      chatId,
      clearDraftChat,
      draftProjectIdRef,
      draftQuizModeRef,
      routeChatId,
      router,
      setMessages,
      setQuizLanguage,
      setQuizVariant,
      resolveQuizVariant,
      setInputRef,
      prepareDraftChat,
      creatingRef,
      setChatId,
    ],
  );

  useEffect(() => {
    if (!token) return;
    const prompt = typeof routePrompt === "string" ? routePrompt.trim() : "";
    const launchId = typeof routeLaunchId === "string" ? routeLaunchId : "";
    if (!prompt || !launchId || handledLaunchIdRef.current === launchId) return;
    handledLaunchIdRef.current = launchId;
    router.setParams({ prompt: undefined, launchId: undefined, chatId: undefined });
    beginChatLaunch(prompt);
  }, [routePrompt, routeLaunchId, token, router, beginChatLaunch]);

  return {
    chatTitle,
    setChatTitle,
    titleGenerating,
    pinned,
    setPinned,
    archived,
    setArchived,
    chatLoading,
    hasMoreOlder,
    loadingOlder,
    loadOlderMessages,
    highlightedMessageId,
    handleFirstReply,
    startNewChat,
    beginChatLaunch,
    pendingLaunch,
    setPendingLaunch,
    pendingLaunchRef,
    pollForTitle,
  };
}

export function useQueuedChatLaunch(
  token: string | null,
  beginChatLaunch: (launch: QueuedChatLaunch | string) => void,
) {
  useFocusEffect(
    useCallback(() => {
      if (!token) return;
      const queued = takeQueuedChatLaunch();
      if (queued) beginChatLaunch(queued);
    }, [token, beginChatLaunch]),
  );
}

import { useCallback, useEffect, useRef, useState } from "react";
import type { FlashListRef } from "@shopify/flash-list";
import { useFocusEffect, useRouter } from "expo-router";
import type { Ionicons } from "@expo/vector-icons";

type Router = ReturnType<typeof useRouter>;

import { insertChatGlobal, patchChatGlobal, setChatTitleGenerating } from "@/lib/drawer";
import { api, type Message } from "@/lib/api";
import { readCachedChatMessages, writeCachedChatMessages } from "@/lib/chatMessageCache";
import { MESSAGE_PAGE_SIZE } from "@/lib/chatConstants";
import type { QueuedChatLaunch } from "@/lib/chatLaunch";
import { takeQueuedChatLaunch } from "@/lib/chatLaunch";
import type { QuizVariant } from "@/lib/quizVariant";
import { quizVariantForProjectKind } from "@/lib/quizVariant";
import type { useDraftChat } from "@/hooks/useDraftChat";

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
  const [titleGenerating, setTitleGenerating] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [chatLoading, setChatLoading] = useState(false);
  const [hasMoreOlder, setHasMoreOlder] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [highlightedMessageId, setHighlightedMessageId] = useState<string | null>(null);
  const [pendingLaunch, setPendingLaunch] = useState<string | null>(null);
  const [dailyQuizActive, setDailyQuizActive] = useState(false);

  const priorRouteChatIdRef = useRef<string | null>(null);
  const pendingHighlightRef = useRef<string | null>(null);
  const highlightLoadInFlightRef = useRef(false);
  const pendingLaunchRef = useRef<string | null>(null);
  const pendingProjectIdRef = useRef<string | null>(null);
  const pendingQuizModeRef = useRef<import("@/lib/quizMode").QuizMode | null>(null);
  const handledLaunchIdRef = useRef<string | null>(null);
  const skipNextFocusRef = useRef(true);

  const pollForTitle = useCallback(async (tid: string, cid: string) => {
    setTitleGenerating(true);
    setChatTitleGenerating(cid);
    try {
      for (let i = 0; i < 5; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        try {
          const updated = await api.getChat(tid, cid);
          if (updated.title) {
            setChatTitle(updated.title);
            patchChatGlobal(cid, { title: updated.title });
            return;
          }
        } catch {
          /* ignore */
        }
      }
    } finally {
      setTitleGenerating(false);
      setChatTitleGenerating(null);
    }
  }, []);

  const handleFirstReply = useCallback(async () => {
    if (!token || !chatId) return;
    try {
      const chat = await api.getChat(token, chatId);
      insertChatGlobal(chat);
    } catch {
      /* drawer insert is best-effort */
    }
    await pollForTitle(token, chatId);
  }, [token, chatId, pollForTitle]);

  useEffect(() => {
    if (!chatId) {
      setTitleGenerating(false);
      setChatTitleGenerating(null);
    }
  }, [chatId]);

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
        draftProjectIdRef.current = chat.project_id ?? null;
        setQuizVariant(resolveQuizVariant(chat.project_id));
        setMessages(page.messages);
        setHasMoreOlder(page.has_more);
        void writeCachedChatMessages(openChatId, page.messages, page.has_more);
        if (!chat.title && page.messages.length > 0) {
          pollForTitle(token, openChatId);
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

      void (async () => {
        try {
          const [chat, page] = await Promise.all([
            api.getChat(token, openChatId),
            api.listMessages(token, openChatId, { limit: MESSAGE_PAGE_SIZE }),
          ]);
          setChatId(chat.id);
          setChatTitle(chat.title);
          setPinned(chat.pinned);
          draftProjectIdRef.current = chat.project_id ?? null;
          setQuizVariant(resolveQuizVariant(chat.project_id));
          setMessages(page.messages);
          setHasMoreOlder(page.has_more);
          void writeCachedChatMessages(openChatId, page.messages, page.has_more);
        } catch {
          /* keep existing messages on silent refetch failure */
        }
      })();
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

  useEffect(() => {
    if (typeof routeHighlightMessage === "string" && routeHighlightMessage) {
      pendingHighlightRef.current = routeHighlightMessage;
      setHighlightedMessageId(routeHighlightMessage);
      router.setParams({ highlightMessage: undefined });
    }
  }, [routeHighlightMessage, router]);

  const tryScrollToHighlight = useCallback(async () => {
    const targetId = pendingHighlightRef.current;
    if (!targetId || messages.length === 0) return;
    const index = messages.findIndex((m) => m.id === targetId);
    if (index >= 0) {
      pendingHighlightRef.current = null;
      requestAnimationFrame(() => {
        listRef.current?.scrollToIndex({
          index,
          animated: true,
          viewPosition: 0.5,
        });
      });
      setTimeout(() => setHighlightedMessageId(null), 3500);
      return;
    }
    if (hasMoreOlder && !loadingOlder && !highlightLoadInFlightRef.current && token && chatId) {
      highlightLoadInFlightRef.current = true;
      try {
        await loadOlderMessages();
      } finally {
        highlightLoadInFlightRef.current = false;
      }
    }
  }, [messages, hasMoreOlder, loadingOlder, token, chatId, loadOlderMessages, listRef]);

  useEffect(() => {
    void tryScrollToHighlight();
  }, [tryScrollToHighlight]);

  const startNewChat = useCallback(() => {
    if (streaming) return;
    discardEmptyChat(chatId);
    clearDraftChat();
    pendingProjectIdRef.current = null;
    setDailyQuizActive(false);
    setInputRef.current("");
    setChatId(null);
    setChatTitle(null);
    setPinned(false);
    setMessages([]);
    setHasMoreOlder(false);
    if (routeChatId != null) {
      router.setParams({ chatId: undefined });
    }
    void prepareDraftChat();
  }, [
    streaming,
    chatId,
    discardEmptyChat,
    clearDraftChat,
    routeChatId,
    router,
    setMessages,
    setInputRef,
    prepareDraftChat,
    setChatId,
  ]);

  const beginChatLaunch = useCallback(
    (launch: QueuedChatLaunch | string) => {
      const queued = typeof launch === "string" ? { prompt: launch.trim() } : launch;
      const isDailyQuiz = Boolean(queued.dailyQuiz && queued.projectId);
      const prompt = queued.prompt?.trim() ?? "";
      if (!isDailyQuiz && !prompt) return;
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
      setMessages([]);
      setHasMoreOlder(false);
      creatingRef.current = false;
      if (routeChatId != null) {
        router.setParams({ chatId: undefined });
      }
      if (isDailyQuiz) {
        pendingLaunchRef.current = null;
        setPendingLaunch(null);
        setDailyQuizActive(true);
      } else {
        setDailyQuizActive(false);
        pendingLaunchRef.current = prompt;
        setPendingLaunch(prompt);
      }
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
    dailyQuizActive,
    setDailyQuizActive,
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

import { useCallback, useEffect, useRef, useState } from "react";
import { AppState, type AppStateStatus } from "react-native";
import type { FlashListRef } from "@shopify/flash-list";
import { useFocusEffect, useRouter } from "expo-router";

import { type IoniconName } from "@/lib/icons";

type Router = ReturnType<typeof useRouter>;

import { api, type Message } from "@/lib/api";
import { getCachedChat } from "@/lib/cache/chatListCache";
import {
  shouldForceForegroundChatRecovery,
  shouldRefetchChatOnForeground,
  shouldSilentRefetchChatOnFocus,
  shouldSkipSilentChatRefetch,
} from "@/lib/chat/chatForegroundRefetch";
import {
  cachedChatPageFetchedAt,
  readCachedChatMessages,
  writeCachedChatMessages,
} from "@/lib/chatMessageCache";
import { mergeLocalAttachmentUris } from "@/lib/chat/chatMessageMerge";
import { MESSAGE_PAGE_SIZE } from "@/lib/chat/chatConstants";
import {
  chatHasThreadContent,
  markChatHasAssistant,
  shouldDiscardOnNewChat,
  shouldProbeEmptyChat,
  shouldProbePreviousChat,
} from "@/lib/chatDraftLogic";
import { shouldInsertDrawerRowOnLeave } from "@/lib/chatTitleRefresh";
import type { QuizVariant } from "@/lib/quizVariant";
import type { useDraftChat } from "@/hooks/useDraftChat";
import { useChatHighlightScroll } from "@/hooks/useChatHighlightScroll";
import { useChatTitlePolling } from "@/hooks/useChatTitlePolling";

type DraftChat = ReturnType<typeof useDraftChat>;

type Options = {
  token: string | null;
  routeChatId: string | undefined;
  routeHighlightMessage: string | undefined;
  router: Router;
  draft: DraftChat;
  chatId: string | null;
  setChatId: React.Dispatch<React.SetStateAction<string | null>>;
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  messages: Message[];
  streaming: boolean;
  /** Latest image-gen in-flight flag — AppState/focus closures must not snapshot it. */
  imageGeneratingRef?: React.MutableRefObject<boolean>;
  stopGeneration: () => void;
  setQuizVariant: React.Dispatch<React.SetStateAction<QuizVariant>>;
  resolveQuizVariant: (projectId: string | null | undefined) => QuizVariant;
  setInputRef: React.MutableRefObject<(value: string) => void>;
  listRef: React.RefObject<FlashListRef<Message> | null>;
  showActionBanner: (message: string, icon?: IoniconName) => void;
  t: (key: string) => string;
};

export function useChatRouteLoader({
  token,
  routeChatId,
  routeHighlightMessage,
  router,
  draft,
  chatId,
  setChatId,
  setMessages,
  messages,
  streaming,
  imageGeneratingRef,
  stopGeneration,
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
    skipLoadForChatIdRef,
    creatingRef,
    discardEmptyChat,
    clearDraftChat,
  } = draft;

  const messagesRef = useRef(messages);
  messagesRef.current = messages;
  const getFirstUserText = useCallback(() => {
    const user = messagesRef.current.find((m) => m.role === "user");
    if (!user) return undefined;
    if (user.content?.trim()) return user.content;
    if (user.local_image_uri) return "[Image: local]";
    if (user.local_file_name || user.local_file_uri) {
      return `[File: ${user.local_file_name ?? "file"}]`;
    }
    return user.content;
  }, []);
  const [chatTitle, setChatTitle] = useState<string | null>(null);
  const { titleGenerating, pollForTitle, handleFirstReply } = useChatTitlePolling({
    token,
    chatId,
    setChatTitle,
    getFirstUserText,
  });
  const [pinned, setPinned] = useState(false);
  const [archived, setArchived] = useState(false);
  const [chatLoading, setChatLoading] = useState(false);
  const [hasMoreOlder, setHasMoreOlder] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);

  const priorRouteChatIdRef = useRef<string | null>(null);
  const skipNextFocusRef = useRef(true);
  const lastSilentFetchAtRef = useRef<Map<string, number>>(new Map());
  const wasStreamingWhenBackgroundedRef = useRef(false);
  // AppState closures must read the latest streaming/loading flags — deps alone
  // would leave a stale "still streaming" view after ws.onclose commits a partial.
  const streamingRef = useRef(streaming);
  const chatLoadingRef = useRef(chatLoading);
  streamingRef.current = streaming;
  chatLoadingRef.current = chatLoading;
  const knownAssistantChatId = chatId ?? (typeof routeChatId === "string" ? routeChatId : null);
  const messagesHadContent = chatHasThreadContent(messages);
  useEffect(() => {
    if (knownAssistantChatId && messagesHadContent) {
      markChatHasAssistant(knownAssistantChatId);
    }
  }, [knownAssistantChatId, messagesHadContent]);

  const turnBusy = () => streamingRef.current || Boolean(imageGeneratingRef?.current);

  const silentRefetchChat = useCallback(
    async (openChatId: string, cancelled: () => boolean, opts?: { force?: boolean }) => {
      if (!token) return;
      if (
        shouldSkipSilentChatRefetch({
          lastFetchedAt: lastSilentFetchAtRef.current.get(openChatId),
          force: opts?.force,
        })
      ) {
        return;
      }
      const disk = await readCachedChatMessages(openChatId);
      if (cancelled()) return;
      if (
        shouldSkipSilentChatRefetch({
          lastFetchedAt: cachedChatPageFetchedAt(disk),
          force: opts?.force,
        })
      ) {
        lastSilentFetchAtRef.current.set(
          openChatId,
          cachedChatPageFetchedAt(disk) ?? Date.now(),
        );
        return;
      }
      try {
        const listed = getCachedChat(openChatId);
        const [chat, page] = await Promise.all([
          listed ?? api.getChat(token, openChatId),
          api.listMessages(token, openChatId, { limit: MESSAGE_PAGE_SIZE }),
        ]);
        if (cancelled()) return;
        setChatId(chat.id);
        setChatTitle(chat.title);
        setPinned(chat.pinned);
        setArchived(Boolean(chat.archived));
        draftProjectIdRef.current = chat.project_id ?? draftProjectIdRef.current;
        setQuizVariant(resolveQuizVariant(chat.project_id));
        setMessages((prev) => mergeLocalAttachmentUris(prev, page.messages));
        setHasMoreOlder(page.has_more);
        lastSilentFetchAtRef.current.set(openChatId, Date.now());
        void writeCachedChatMessages(openChatId, page.messages, page.has_more);
      } catch {
        /* keep existing messages on silent refetch failure */
      }
    },
    [token, setChatId, setMessages, draftProjectIdRef, setQuizVariant, resolveQuizVariant],
  );

  useEffect(() => {
    let cancelled = false;
    const onAppState = (state: AppStateStatus) => {
      if (state === "background" || state === "inactive") {
        if (streamingRef.current || Boolean(imageGeneratingRef?.current)) {
          wasStreamingWhenBackgroundedRef.current = true;
        }
        const draftId = draftChatIdRef.current;
        if (!draftId) return;
        // Empty pre-created drafts should not survive backgrounding.
        if (messages.length === 0 && chatId == null) {
          discardEmptyChat(draftId);
          clearDraftChat();
        }
        return;
      }
      // Backgrounding mid-stream kills the socket; onclose commits a truncated
      // bubble. When we return to foreground with streaming finished, pull the
      // server's full reply without requiring the user to leave the chat.
      const openChatId =
        (typeof routeChatId === "string" ? routeChatId : null) ?? chatId;
      if (
        !openChatId ||
        !shouldRefetchChatOnForeground({
          appState: state,
          token,
          chatId: openChatId,
          streaming: streamingRef.current,
          chatLoading: chatLoadingRef.current,
          imageGenerating: Boolean(imageGeneratingRef?.current),
        })
      ) {
        return;
      }
      const force = shouldForceForegroundChatRecovery({
        wasStreamingWhenBackgrounded: wasStreamingWhenBackgroundedRef.current,
      });
      wasStreamingWhenBackgroundedRef.current = false;
      skipNextFocusRef.current = true;
      void silentRefetchChat(openChatId, () => cancelled, { force });
    };
    const sub = AppState.addEventListener("change", onAppState);
    return () => {
      cancelled = true;
      sub.remove();
    };
  }, [
    messages.length,
    chatId,
    routeChatId,
    token,
    discardEmptyChat,
    clearDraftChat,
    draftChatIdRef,
    silentRefetchChat,
  ]);

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
      if (
        shouldProbePreviousChat({
          chatId: prevOpenChatId,
          messagesHadAssistant: chatHasThreadContent(messagesRef.current),
        })
      ) {
        discardEmptyChat(prevOpenChatId);
      }
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
        lastSilentFetchAtRef.current.set(openChatId, Date.now());
        return;
      }
      setChatLoading(true);
      setHasMoreOlder(false);
      try {
        const cached = await readCachedChatMessages(openChatId);
        if (cancelled) return;
        const listed = getCachedChat(openChatId);
        if (cached) {
          setChatId(openChatId);
          setMessages((prev) => mergeLocalAttachmentUris(prev, cached.messages));
          setHasMoreOlder(cached.has_more);
          setChatLoading(false);
          if (listed) {
            setChatTitle(listed.title);
            setPinned(listed.pinned);
            setArchived(Boolean(listed.archived));
            draftProjectIdRef.current = listed.project_id ?? draftProjectIdRef.current;
            setQuizVariant(resolveQuizVariant(listed.project_id));
            lastSilentFetchAtRef.current.set(
              openChatId,
              cachedChatPageFetchedAt(cached) ?? Date.now(),
            );
            return;
          }
        }
        const [chat, page] = await Promise.all([
          listed ?? api.getChat(token, openChatId),
          cached
            ? Promise.resolve({ messages: cached.messages, has_more: cached.has_more })
            : api.listMessages(token, openChatId, { limit: MESSAGE_PAGE_SIZE }),
        ]);
        if (cancelled) return;
        setChatId(chat.id);
        setChatTitle(chat.title);
        setPinned(chat.pinned);
        setArchived(Boolean(chat.archived));
        draftProjectIdRef.current = chat.project_id ?? draftProjectIdRef.current;
        setQuizVariant(resolveQuizVariant(chat.project_id));
        setMessages((prev) => mergeLocalAttachmentUris(prev, page.messages));
        setHasMoreOlder(page.has_more);
        lastSilentFetchAtRef.current.set(openChatId, Date.now());
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
      if (!shouldSilentRefetchChatOnFocus()) return;
      if (!token || !openChatId || turnBusy() || chatLoading) return;

      let cancelled = false;
      void silentRefetchChat(openChatId, () => cancelled);
      return () => {
        cancelled = true;
      };
    }, [token, routeChatId, chatLoading, silentRefetchChat]),
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

  const leaveOpenChat = useCallback(
    (opts?: { force?: boolean }) => {
      // Stop only when the open chat is being deleted. New chat / Home launch
      // must leave the in-flight reply running so it can finish in the background.
      if (opts?.force && turnBusy()) stopGeneration();
      const leavingMessages = messagesRef.current;
      if (shouldInsertDrawerRowOnLeave(leavingMessages)) {
        void handleFirstReply();
      }
      if (
        shouldDiscardOnNewChat(routeChatId) &&
        shouldProbeEmptyChat(chatHasThreadContent(leavingMessages))
      ) {
        discardEmptyChat(chatId);
      }
      clearDraftChat();
    },
    [
      stopGeneration,
      handleFirstReply,
      routeChatId,
      discardEmptyChat,
      chatId,
      clearDraftChat,
    ],
  );

  const startNewChat = useCallback(
    (_opts?: { force?: boolean }) => {
      leaveOpenChat(_opts);
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
    },
    [
      leaveOpenChat,
      routeChatId,
      router,
      setMessages,
      setInputRef,
      setChatId,
    ],
  );

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
    pollForTitle,
  };
}

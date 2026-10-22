import { useCallback, useEffect, useRef, useState } from "react";
import { AppState, type AppStateStatus } from "react-native";
import type { FlashListRef } from "@shopify/flash-list";
import { useFocusEffect, useRouter } from "expo-router";

import type { IconName } from "@/ui/icons/names";

import { useComposerDraftApiOptional } from "@/contexts/ComposerDraftContext";
import { api, type Chat, type Message } from "@/lib/api";
import { ApiRequestError } from "@/lib/api/client";
import { getSessionGeneration } from "@/lib/auth";
import { getCachedChat, getFetchedChat } from "@/lib/cache/chatListCache";
import {
  shouldForceForegroundChatRecovery,
  shouldRefetchChatOnForeground,
  shouldSilentRefetchChatOnFocus,
  shouldSkipSilentChatRefetch,
} from "@/features/chat/model/foregroundRefetch";
import {
  cachedChatPageFetchedAt,
  clearCachedChatMessages,
  isCachedChatPageFresh,
  markCachedChatPagesStale,
  peekCachedChatPage,
  readCachedChatMessages,
  type CachedChatPage,
} from "@/features/chat/model/messageCache";
import { mergeLocalAttachmentUris, mergeOpenedPage, paintCachedThread, addedSincePaint } from "@/features/chat/model/messageMerge";
import { MESSAGE_PAGE_SIZE } from "@/features/chat/model/constants";
import { beginOpenedPageRead, type OpenedPageRead } from "@/features/chat/model/openedPage";
import {
  chatHasThreadContent,
  markChatHasAssistant,
  shouldDiscardOnNewChat,
  shouldProbeEmptyChat,
  shouldProbePreviousChat,
} from "@/features/chat/model/draftLogic";
import { shouldInsertDrawerRowOnLeave } from "@/features/chat/model/titleRefresh";
import { getChatMutationRevision, removeChatGlobal, subscribeChatChanges } from "@/lib/drawer";
import type { useDraftChat } from "@/features/chat/hooks/useDraftChat";
import { useChatHighlightScroll } from "@/features/chat/hooks/useChatHighlightScroll";
import { useChatOlderMessages } from "@/features/chat/hooks/useChatOlderMessages";
import { useChatPageCacheWriter, type ChatPageSync } from "@/features/chat/hooks/useChatPageCacheWriter";
import { useChatTitlePolling } from "@/features/chat/hooks/useChatTitlePolling";

type Router = ReturnType<typeof useRouter>;
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
  listRef: React.RefObject<FlashListRef<Message> | null>;
  showActionBanner: (message: string, icon?: IconName) => void;
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
  listRef,
  showActionBanner,
  t,
}: Options) {
  const {
    draftChatIdRef,
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
  const [pageSync, setPageSync] = useState<ChatPageSync | null>(null);
  const composer = useComposerDraftApiOptional();
  const session = getSessionGeneration();
  const signedIn = Boolean(token);
  const viewRef = useRef({ session, routeChatId, version: 0 });
  if (viewRef.current.session !== session || viewRef.current.routeChatId !== routeChatId) {
    viewRef.current = { session, routeChatId, version: viewRef.current.version + 1 };
  }
  const viewVersion = viewRef.current.version;
  const activeChatRef = useRef(chatId);
  activeChatRef.current = chatId;
  const isActiveChat = useCallback((id: string) => id === activeChatRef.current, []);
  const { hasMoreOlder, setHasMoreOlder, loadingOlder, loadOlderMessages, resetOlder } = useChatOlderMessages({
    token, chatId, chatLoading, messages, setMessages, viewRef, isActiveChat, showActionBanner, t,
  });
  useEffect(() => subscribeChatChanges((id, patch) => {
    if (session !== getSessionGeneration() || id !== activeChatRef.current || !patch) return;
    if (patch.title !== undefined) setChatTitle(patch.title);
    if (patch.pinned !== undefined) setPinned(patch.pinned);
    if (patch.archived !== undefined) setArchived(Boolean(patch.archived));
  }), [session]);

  const applyMetadata = useCallback((chat: Chat | undefined) => {
    if (!chat) return;
    setChatTitle(chat.title);
    setPinned(chat.pinned);
    setArchived(Boolean(chat.archived));
  }, []);
  useEffect(() => () => {
    viewRef.current.version += 1;
  }, []);

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

  const turnBusy = useCallback(
    () => streamingRef.current || Boolean(imageGeneratingRef?.current),
    [imageGeneratingRef],
  );

  const leaveOpenChat = useCallback(
    (opts?: { force?: boolean }) => {
      // Stop only when the open chat is being deleted. New chat / Home launch
      // must leave the in-flight reply running so it can finish in the background.
      if (opts?.force && turnBusy()) stopGeneration();
      const leavingMessages = messagesRef.current;
      if (!opts?.force && shouldInsertDrawerRowOnLeave(leavingMessages)) {
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
      turnBusy,
      handleFirstReply,
      routeChatId,
      discardEmptyChat,
      chatId,
      clearDraftChat,
    ],
  );

  const startNewChat = useCallback(
    (_opts?: { force?: boolean }) => {
      viewRef.current.version++;
      resetOlder();
      leaveOpenChat(_opts);
      setChatId(null);
      setChatTitle(null);
      setPinned(false);
      setArchived(false);
      setMessages([]);
      setHasMoreOlder(false);
      setChatLoading(false);
      if (routeChatId != null) {
        router.setParams({ chatId: undefined });
      }
    },
    [
      leaveOpenChat,
      routeChatId,
      router,
      setMessages,
      setChatId,
      resetOlder,
      setHasMoreOlder,
    ],
  );

  const silentRefetchChat = useCallback(
    async (openChatId: string, cancelled: () => boolean, opts?: { force?: boolean }) => {
      if (!token || session !== getSessionGeneration() || viewVersion !== viewRef.current.version ||
          openChatId !== activeChatRef.current) return;
      const version = viewVersion;
      const ownerSession = getSessionGeneration();
      const previousMessages = messagesRef.current;
      const stale = () =>
        cancelled() || ownerSession !== getSessionGeneration() || version !== viewRef.current.version ||
        turnBusy() || messagesRef.current !== previousMessages;
      if (
        shouldSkipSilentChatRefetch({
          lastFetchedAt: lastSilentFetchAtRef.current.get(openChatId),
          force: opts?.force,
        })
      ) {
        return;
      }
      const disk = peekCachedChatPage(openChatId) ?? await readCachedChatMessages(openChatId);
      if (stale()) return;
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
        const revision = getChatMutationRevision(openChatId);
        const [chat, page] = await Promise.all([
          getFetchedChat(openChatId) ?? api.getChat(token, openChatId),
          api.listMessages(token, openChatId, { limit: MESSAGE_PAGE_SIZE }),
        ]);
        if (stale()) return;
        setChatId(chat.id);
        applyMetadata(revision === getChatMutationRevision(openChatId) ? chat : getCachedChat(openChatId));
        setMessages((prev) => mergeLocalAttachmentUris(prev, page.messages));
        setHasMoreOlder(page.has_more);
        const fetchedAt = Date.now();
        lastSilentFetchAtRef.current.set(openChatId, fetchedAt);
        setPageSync({ chatId: openChatId, fetchedAt });
      } catch {
        /* keep existing messages on silent refetch failure */
      }
    },
    [token, session, viewVersion, setChatId, setMessages, applyMetadata, turnBusy, setHasMoreOlder],
  );

  useEffect(() => {
    let cancelled = false;
    const onAppState = (state: AppStateStatus) => {
      if (session !== getSessionGeneration()) return;
      if (state === "background" || state === "inactive") {
        // Another device may write to any chat while this one is away.
        if (state === "background") markCachedChatPagesStale();
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
    session,
    imageGeneratingRef,
  ]);

  useEffect(() => {
    skipNextFocusRef.current = true;
  }, [routeChatId]);

  useEffect(() => {
    resetOlder();
    setPageSync(null);
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
    let opened: OpenedPageRead | null = null;
    const version = viewRef.current.version;
    const isCurrent = () => !cancelled && session === getSessionGeneration() && version === viewRef.current.version;
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
        // The chat this view just created holds nothing but what it shows.
        lastSilentFetchAtRef.current.set(openChatId, Date.now());
        setPageSync({ chatId: openChatId, fetchedAt: Date.now() });
        return;
      }
      const showCachedPage = (cached: CachedChatPage | null, listed = getCachedChat(openChatId)) => {
        setChatId(openChatId);
        setMessages((prev) => paintCachedThread(prev, cached?.messages ?? []));
        setChatTitle(null);
        setPinned(false);
        setArchived(false);
        if (cached) {
          setHasMoreOlder(cached.has_more);
          if (listed) applyMetadata(listed);
        }
      };
      const kept = peekCachedChatPage(openChatId);
      const listed = getFetchedChat(openChatId);
      if (kept && listed && isCachedChatPageFresh(openChatId, listed.updated_at)) {
        // This device wrote the page moments ago and nothing suggests the chat moved on.
        showCachedPage(kept, listed);
        const fetchedAt = cachedChatPageFetchedAt(kept) ?? Date.now();
        lastSilentFetchAtRef.current.set(openChatId, fetchedAt);
        setPageSync({ chatId: openChatId, fetchedAt });
        setChatLoading(false);
        if (!listed.title && kept.messages.length > 0) pollForTitle(token, openChatId);
        return;
      }
      setChatLoading(true);
      setHasMoreOlder(false);
      // Send works once the cached page is painted; a turn sent before the page lands waits for it.
      const read = beginOpenedPageRead(openChatId);
      opened = read;
      try {
        // Stale-while-revalidate: keep the previous thread painted during the
        // (fast) cache read, then swap in one shot — no blank flash on open.
        // The old thread's pending work still cannot paint into this route
        // because every set below is guarded by isCurrent().
        const cached = kept ?? await readCachedChatMessages(openChatId);
        if (!isCurrent()) return;
        showCachedPage(cached);
        const painted = new Set(cached?.messages.map((m) => m.id));
        const revision = getChatMutationRevision(openChatId);
        const [chat, page] = await Promise.all([
          getFetchedChat(openChatId) ?? api.getChat(token, openChatId),
          api.listMessages(token, openChatId, { limit: MESSAGE_PAGE_SIZE }),
        ]);
        if (!isCurrent()) return;
        setChatId(chat.id);
        const currentChat = revision === getChatMutationRevision(openChatId) ? chat : getCachedChat(openChatId);
        applyMetadata(currentChat);
        // A turn that went out before the page may be in it: merge once nothing of it is on screen, else reread later.
        if (read.release() || !addedSincePaint(messagesRef.current, page.messages, painted)) {
          setMessages((prev) => mergeOpenedPage(prev, page.messages, painted));
          setHasMoreOlder(page.has_more);
          const fetchedAt = Date.now();
          lastSilentFetchAtRef.current.set(openChatId, fetchedAt);
          setPageSync({ chatId: openChatId, fetchedAt });
        } else setPageSync({ chatId: openChatId, fetchedAt: null });
        if (currentChat && !currentChat.title && page.messages.length > 0) {
          pollForTitle(token, openChatId);
        }
      } catch (error) {
        if (isCurrent()) {
          if (error instanceof ApiRequestError && error.status === 404) {
            read.chatGone(composer);
            removeChatGlobal(openChatId);
            void clearCachedChatMessages(openChatId);
            startNewChat({ force: true });
          }
          showActionBanner(t("common.error"), "alert-circle");
        }
      } finally {
        // A read that failed lets a turn waiting for it go out.
        if (isCurrent()) read.release();
        if (isCurrent()) setChatLoading(false);
      }
    })();
    return () => {
      cancelled = true;
      // Left before the page landed: a turn waiting for it goes back to this chat's composer (not past sign-out).
      opened?.cancel(session === getSessionGeneration() ? composer : null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signedIn, session, routeChatId]);

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
    }, [token, routeChatId, chatLoading, silentRefetchChat, turnBusy]),
  );

  useChatPageCacheWriter({
    chatId, routeChatId, messages, busy: streaming, hasMoreOlder, sync: pageSync, resync: silentRefetchChat,
  });

  const { highlightedMessageId } = useChatHighlightScroll({
    chatLoading,
    routeChatId,
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

  return {
    chatTitle,
    setChatTitle,
    titleGenerating,
    pinned,
    setPinned,
    archived,
    setArchived,
    chatLoading,
    // Send waits only while nothing of the routed chat is on screen.
    historyPending: chatLoading && (messages.length === 0 || chatId !== (routeChatId ?? null)),
    hasMoreOlder,
    loadingOlder,
    loadOlderMessages,
    highlightedMessageId,
    handleFirstReply,
    startNewChat,
    pollForTitle,
  };
}

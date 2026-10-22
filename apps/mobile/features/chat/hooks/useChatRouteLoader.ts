import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { AppStateStatus } from "react-native";
import type { FlashListRef } from "@shopify/flash-list";
import type { useRouter } from "expo-router";

import type { IconName } from "@/ui/icons/names";

import { api, type Chat, type Message } from "@/lib/api";
import { ApiRequestError } from "@/lib/api/client";
import { getSessionGeneration } from "@/lib/auth";
import { getCachedChat } from "@/features/chat/model/chatListCache";
import { onAppStateChange } from "@/lib/foregroundRefresh";
import {
  shouldForceForegroundChatRecovery,
  shouldRefetchChatOnForeground,
  shouldSkipSilentChatRefetch,
} from "@/features/chat/model/foregroundRefetch";
import { keepLeftThread, takeRecentLeftThread, type LeftThread } from "@/features/chat/model/leftThreads";
import {
  cachedChatPageFetchedAt,
  clearCachedChatMessages,
  readCachedChatMessages,
  writeCachedChatMessages,
} from "@/features/chat/model/messageCache";
import { mergeLocalAttachmentUris } from "@/features/chat/model/messageMerge";
import { MESSAGE_PAGE_SIZE } from "@/features/chat/model/constants";
import {
  chatHasThreadContent,
  markChatHasAssistant,
  shouldDiscardOnNewChat,
  shouldProbeEmptyChat,
  shouldProbePreviousChat,
} from "@/features/chat/model/draftLogic";
import { shouldInsertDrawerRowOnLeave } from "@/features/chat/model/titleRefresh";
import { getChatMutationRevision, removeChatGlobal, subscribeChatChanges } from "@/features/chat/drawer/drawer";
import type { useDraftChat } from "@/features/chat/hooks/useDraftChat";
import { useChatHighlightScroll } from "@/features/chat/hooks/useChatHighlightScroll";
import { useChatPaging } from "@/features/chat/hooks/useChatPaging";
import { useChatTitlePolling } from "@/features/chat/hooks/useChatTitlePolling";
import { useLatestRef } from "@/lib/latestRef";
import { useViewOwner } from "@/lib/viewOwner";

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

  const messagesRef = useLatestRef(messages);
  const getFirstUserText = useCallback(() => {
    const user = messagesRef.current.find((m) => m.role === "user");
    if (!user) return undefined;
    if (user.content?.trim()) return user.content;
    if (user.local_image_uri) return "[Image: local]";
    if (user.local_file_name || user.local_file_uri) {
      return `[File: ${user.local_file_name ?? "file"}]`;
    }
    return user.content;
  }, [messagesRef]);
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
  const session = getSessionGeneration();
  const signedIn = Boolean(token);
  // Bumped by each new route or account, New chat and unmount: a read from before lands nowhere.
  const viewRef = useRef({ version: 0 });
  useLayoutEffect(() => {
    viewRef.current.version += 1;
  }, [session, routeChatId]);
  const { owns } = useViewOwner(`${session}:${routeChatId}`);
  const activeChatRef = useLatestRef(chatId);
  useEffect(() => subscribeChatChanges((id, patch) => {
    if (session !== getSessionGeneration() || id !== activeChatRef.current || !patch) return;
    if (patch.title !== undefined) setChatTitle(patch.title);
    if (patch.pinned !== undefined) setPinned(patch.pinned);
    if (patch.archived !== undefined) setArchived(Boolean(patch.archived));
  }), [session, activeChatRef]);

  const applyMetadata = useCallback((chat: Chat | undefined) => {
    if (!chat) return;
    setChatTitle(chat.title);
    setPinned(chat.pinned);
    setArchived(Boolean(chat.archived));
  }, []);
  const paging = useChatPaging({ token, chatId, chatLoading, messages, setMessages, hasMoreOlder, setHasMoreOlder,
    viewRef, activeChatRef, showActionBanner, t });
  const { resetPaging, hasMoreNewer } = paging;
  useEffect(() => () => {
    viewRef.current.version += 1;
  }, []);

  const priorRouteChatIdRef = useRef<string | null>(null);
  const leftThreadsRef = useRef(new Map<string, LeftThread>());
  const hasMoreOlderRef = useLatestRef(hasMoreOlder);
  const lastSilentFetchAtRef = useRef<Map<string, number>>(new Map());
  const wasStreamingWhenBackgroundedRef = useRef(false);
  // AppState closures must read the latest streaming/loading flags — deps alone
  // would leave a stale "still streaming" view after ws.onclose commits a partial.
  const streamingRef = useLatestRef(streaming);
  const chatLoadingRef = useLatestRef(chatLoading);
  const knownAssistantChatId = chatId ?? (typeof routeChatId === "string" ? routeChatId : null);
  const messagesHadContent = chatHasThreadContent(messages);
  useEffect(() => {
    if (knownAssistantChatId && messagesHadContent) {
      markChatHasAssistant(knownAssistantChatId);
    }
  }, [knownAssistantChatId, messagesHadContent]);

  const turnBusy = useCallback(
    () => streamingRef.current || Boolean(imageGeneratingRef?.current),
    [imageGeneratingRef, streamingRef],
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
      messagesRef,
    ],
  );

  const startNewChat = useCallback(
    (_opts?: { force?: boolean }) => {
      viewRef.current.version++;
      resetPaging();
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
      resetPaging,
      routeChatId,
      router,
      setMessages,
      setChatId,
    ],
  );


  const silentRefetchChat = useCallback(
    async (openChatId: string, cancelled: () => boolean, opts?: { force?: boolean }) => {
      if (!token || session !== getSessionGeneration() || !owns() ||
          openChatId !== activeChatRef.current || hasMoreNewer) return;
      const version = viewRef.current.version;
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
      const disk = await readCachedChatMessages(openChatId);
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
        const listed = getCachedChat(openChatId);
        const revision = getChatMutationRevision(openChatId);
        const [chat, page] = await Promise.all([
          listed ?? api.getChat(token, openChatId),
          api.listMessages(token, openChatId, { limit: MESSAGE_PAGE_SIZE }),
        ]);
        if (stale()) return;
        setChatId(chat.id);
        applyMetadata(revision === getChatMutationRevision(openChatId) ? chat : getCachedChat(openChatId));
        setMessages((prev) => mergeLocalAttachmentUris(prev, page.messages));
        setHasMoreOlder(page.has_more);
        lastSilentFetchAtRef.current.set(openChatId, Date.now());
        void writeCachedChatMessages(openChatId, page.messages, page.has_more);
      } catch {
        /* keep existing messages on silent refetch failure */
      }
    },
    [token, session, owns, activeChatRef, messagesRef, setChatId, setMessages, applyMetadata, turnBusy, hasMoreNewer],
  );

  useEffect(() => {
    let cancelled = false;
    const onAppState = (state: AppStateStatus) => {
      if (session !== getSessionGeneration()) return;
      if (state === "background" || state === "inactive") {
        if (streamingRef.current || Boolean(imageGeneratingRef?.current)) {
          wasStreamingWhenBackgroundedRef.current = true;
        }
        // An unused draft is dropped by useDraftChat, once, on background.
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
      void silentRefetchChat(openChatId, () => cancelled, { force });
    };
    const stopAppState = onAppStateChange(onAppState);
    return () => {
      cancelled = true;
      stopAppState();
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
    chatLoadingRef,
    streamingRef,
  ]);

  useEffect(() => {
    resetPaging();
    if (!token) {
      setChatLoading(false);
      return;
    }
    const openChatId = typeof routeChatId === "string" ? routeChatId : null;
    const prevOpenChatId = priorRouteChatIdRef.current;
    if (prevOpenChatId && prevOpenChatId !== openChatId && activeChatRef.current === prevOpenChatId &&
        !turnBusy() && chatHasThreadContent(messagesRef.current)) {
      keepLeftThread(leftThreadsRef.current, prevOpenChatId,
        { messages: messagesRef.current, hasMore: hasMoreOlderRef.current, at: Date.now() });
    }
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
        lastSilentFetchAtRef.current.set(openChatId, Date.now());
        return;
      }
      const left = takeRecentLeftThread(leftThreadsRef.current, openChatId);
      const listedChat = getCachedChat(openChatId);
      if (left && listedChat) {
        setChatId(openChatId);
        setMessages(left.messages);
        setHasMoreOlder(left.hasMore);
        applyMetadata(listedChat);
        setChatLoading(false);
        return;
      }
      setChatLoading(true);
      setHasMoreOlder(false);
      try {
        // Stale-while-revalidate: keep the previous thread painted during the
        // (fast) cache read, then swap in one shot — no blank flash on open.
        // The old thread's pending work still cannot paint into this route
        // because every set below is guarded by isCurrent().
        const cached = await readCachedChatMessages(openChatId);
        if (!isCurrent()) return;
        const listed = getCachedChat(openChatId);
        setChatId(openChatId);
        setMessages((prev) => {
          const incoming = cached?.messages ?? [];
          // Orphan local-URI carry-over only makes sense when prev is the same
          // thread; on a chat swap it could leak the old chat's local image
          // onto the new chat's row.
          const incomingIds = new Set(incoming.map((m) => m.id));
          const sameThread = prev.some((m) => incomingIds.has(m.id));
          return sameThread ? mergeLocalAttachmentUris(prev, incoming) : incoming;
        });
        setChatTitle(null);
        setPinned(false);
        setArchived(false);
        if (cached) {
          setHasMoreOlder(cached.has_more);
          if (listed) {
            applyMetadata(listed);
          }
        }
        const revision = getChatMutationRevision(openChatId);
        const [chat, page] = await Promise.all([
          listed ?? api.getChat(token, openChatId),
          api.listMessages(token, openChatId, { limit: MESSAGE_PAGE_SIZE }),
        ]);
        if (!isCurrent()) return;
        setChatId(chat.id);
        const currentChat = revision === getChatMutationRevision(openChatId) ? chat : getCachedChat(openChatId);
        applyMetadata(currentChat);
        setMessages((prev) => mergeLocalAttachmentUris(prev, page.messages));
        setHasMoreOlder(page.has_more);
        lastSilentFetchAtRef.current.set(openChatId, Date.now());
        void writeCachedChatMessages(openChatId, page.messages, page.has_more);
        if (currentChat && !currentChat.title && page.messages.length > 0) {
          pollForTitle(token, openChatId);
        }
      } catch (error) {
        if (isCurrent()) {
          if (error instanceof ApiRequestError && error.status === 404) {
            removeChatGlobal(openChatId);
            void clearCachedChatMessages(openChatId);
            startNewChat({ force: true });
          }
          showActionBanner(t("common.error"), "alert-circle");
        }
      } finally {
        if (isCurrent()) setChatLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signedIn, session, routeChatId]);

  const { highlightedMessageId } = useChatHighlightScroll({
    chatLoading, routeChatId, routeHighlightMessage, router, messages, hasMoreOlder, hasMoreNewer,
    token, chatId, openAround: paging.openAround, listRef,
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
    hasMoreOlder,
    loadingOlder: paging.loadingOlder,
    loadOlderMessages: paging.loadOlderMessages,
    newerPage: paging.newerPage,
    jumpToLatest: paging.jumpToLatest,
    highlightedMessageId,
    handleFirstReply,
    startNewChat,
    pollForTitle,
  };
}

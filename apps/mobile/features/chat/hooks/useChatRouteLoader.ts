import { useCallback, useEffect, useLayoutEffect, useRef, useState, type MutableRefObject } from "react";
import type { FlashListRef } from "@shopify/flash-list";
import type { useRouter } from "expo-router";

import type { IconName } from "@/ui/icons/names";

import type { Message } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import {
  chatHasThreadContent,
  markChatHasAssistant,
  shouldDiscardOnNewChat,
  shouldProbeEmptyChat,
} from "@/features/chat/model/draftLogic";
import { shouldInsertDrawerRowOnLeave } from "@/features/chat/model/titleRefresh";
import type { useDraftChat } from "@/features/chat/hooks/useDraftChat";
import { useChatHighlightScroll } from "@/features/chat/hooks/useChatHighlightScroll";
import type { ChatMetadata } from "@/features/chat/hooks/useChatMetadata";
import { useChatPaging } from "@/features/chat/hooks/useChatPaging";
import { useChatPageCacheWriter, useChatPageSync } from "@/features/chat/hooks/useChatPageCacheWriter";
import { useChatPendingPhotoRead } from "@/features/chat/hooks/useChatPendingPhotoRead";
import { useChatPageReconnect } from "@/features/chat/hooks/useChatPageReconnect";
import { useForegroundRefetch, useSilentRefetchChat } from "@/features/chat/hooks/useChatRefetch";
import { useChatRouteOpen } from "@/features/chat/hooks/useChatRouteOpen";
import { useChatTitle } from "@/features/chat/hooks/useChatTitle";
import type { FirstReply } from "@/features/chat/model/chatTurnCore";
import { useLatestRef } from "@/lib/latestRef";
import type { EditThread } from "@/features/chat/model/threadEdit";

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
  /** Changes the thread on screen; useChat owns it. */
  editThread: EditThread;
  messages: Message[];
  streaming: boolean;
  /** A picture is being made: the turn is busy, as while a reply streams. */
  imageGenerating?: boolean;
  stopGeneration: () => void;
  listRef: React.RefObject<FlashListRef<Message> | null>;
  /** The open chat's title and flags (useChatMetadata): an open sets them, leaving puts them back. */
  metadata: Pick<ChatMetadata, "setChatTitle" | "applyMetadata" | "resetMetadata">;
  showActionBanner: (message: string, icon?: IconName) => void;
  t: (key: string) => string;
};

/** The first user turn's words, or what it carried, for the chat's provisional drawer row. */
function firstUserText(messages: Message[]): string | undefined {
  const user = messages.find((m) => m.role === "user");
  if (!user) return undefined;
  if (user.content?.trim()) return user.content;
  if (user.local_image_uri) return "[Image: local]";
  if (user.local_file_name || user.local_file_uri) {
    return `[File: ${user.local_file_name ?? "file"}]`;
  }
  return user.content;
}

/**
 * Bumped by each new route or account, New chat and unmount: a read from before lands nowhere.
 * This hook's one view guard: New chat moves it at once, which a view keyed on the route cannot.
 */
function useViewVersion(session: number, routeChatId: string | undefined): MutableRefObject<{ version: number }> {
  const viewRef = useRef({ version: 0 });
  useLayoutEffect(() => {
    viewRef.current.version += 1;
  }, [session, routeChatId]);
  useEffect(() => () => {
    viewRef.current.version += 1;
  }, []);
  return viewRef;
}

type LeaveOptions = Pick<Options, "routeChatId" | "chatId" | "stopGeneration"> & {
  draft: Pick<DraftChat, "discardEmptyChat" | "clearDraftChat">;
  messagesRef: React.RefObject<Message[]>;
  turnBusy: () => boolean;
  handleFirstReply: (explicitChatId?: string | null, reply?: FirstReply) => Promise<void>;
};

/** Leaves the open chat: its row reaches the drawer, an empty one goes, the draft is dropped. */
function useLeaveOpenChat({ routeChatId, chatId, stopGeneration, draft, messagesRef, turnBusy, handleFirstReply }: LeaveOptions) {
  const { discardEmptyChat, clearDraftChat } = draft;
  return useCallback(
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
    [stopGeneration, turnBusy, handleFirstReply, routeChatId, discardEmptyChat, chatId, clearDraftChat, messagesRef],
  );
}

export function useChatRouteLoader({
  token, routeChatId, routeHighlightMessage, router, draft, chatId, setChatId, editThread, messages, streaming,
  imageGenerating = false, stopGeneration, listRef, metadata, showActionBanner, t,
}: Options) {
  const messagesRef = useLatestRef(messages);
  const getFirstUserText = useCallback(() => firstUserText(messagesRef.current), [messagesRef]);
  const { setChatTitle, applyMetadata, resetMetadata } = metadata;
  const { titleGenerating, awaitTitle, handleFirstReply } = useChatTitle({
    token, chatId, setChatTitle, getFirstUserText,
  });
  const [chatLoading, setChatLoading] = useState(false);
  const [hasMoreOlder, setHasMoreOlder] = useState(false);
  const { sync: pageSync, notePageRead, notePageUnmerged, clearPageSync } = useChatPageSync();
  const viewRef = useViewVersion(getSessionGeneration(), routeChatId);
  const activeChatRef = useLatestRef(chatId);
  const paging = useChatPaging({ token, chatId, chatLoading, messages, editThread, hasMoreOlder, setHasMoreOlder,
    viewRef, activeChatRef, showActionBanner, t });
  const { resetPaging, hasMoreNewer } = paging;

  // AppState closures must read the latest streaming/loading flags.
  const streamingRef = useLatestRef(streaming);
  const chatLoadingRef = useLatestRef(chatLoading);
  const imageGeneratingRef = useLatestRef(imageGenerating);
  const knownAssistantChatId = chatId ?? routeChatId ?? null;
  const messagesHadContent = chatHasThreadContent(messages);
  useEffect(() => {
    if (knownAssistantChatId && messagesHadContent) markChatHasAssistant(knownAssistantChatId);
  }, [knownAssistantChatId, messagesHadContent]);
  const turnBusy = useCallback(
    () => streamingRef.current || imageGeneratingRef.current,
    [imageGeneratingRef, streamingRef],
  );

  /** No chat on screen: what Home and New chat show. */
  const clearView = useCallback(() => {
    setChatId(null);
    resetMetadata();
    editThread([], "view_cleared");
    setHasMoreOlder(false);
  }, [setChatId, resetMetadata, editThread]);
  const leaveOpenChat = useLeaveOpenChat({ routeChatId, chatId, stopGeneration, draft, messagesRef, turnBusy, handleFirstReply });
  const startNewChat = useCallback(
    (opts?: { force?: boolean }) => {
      viewRef.current.version++;
      resetPaging();
      leaveOpenChat(opts);
      clearView();
      setChatLoading(false);
      if (routeChatId != null) router.setParams({ chatId: undefined });
    },
    [viewRef, leaveOpenChat, resetPaging, clearView, routeChatId, router],
  );

  const silentRefetchChat = useSilentRefetchChat({ token, viewRef, activeChatRef, messagesRef, setChatId, editThread,
    setHasMoreOlder, applyMetadata, notePageRead, turnBusy, hasMoreNewer });
  useForegroundRefetch({ token, chatId, routeChatId, streamingRef, chatLoadingRef, imageGeneratingRef,
    refetch: silentRefetchChat });
  useChatRouteOpen({ token, routeChatId, viewRef, draft, messagesRef, setChatId, setChatLoading, setHasMoreOlder,
    editThread, applyMetadata, resetMetadata, clearView, notePageRead, notePageUnmerged, clearPageSync, resetPaging,
    awaitTitle, startNewChat, showActionBanner, t });
  useChatPageCacheWriter({
    chatId, routeChatId, messages, busy: streaming, hasMoreOlder, hasMoreNewer, sync: pageSync,
    resync: silentRefetchChat,
  });
  useChatPageReconnect({ chatId, busy: () => chatLoadingRef.current || turnBusy(), refetch: silentRefetchChat });
  useChatPendingPhotoRead({ chatId, messages, busy: chatLoading || streaming || imageGenerating, refetch: silentRefetchChat });

  const { highlightedMessageId } = useChatHighlightScroll({
    chatLoading, routeChatId, routeHighlightMessage, router, messages, hasMoreOlder, hasMoreNewer,
    token, chatId, openAround: paging.openAround, listRef,
  });

  return {
    titleGenerating,
    chatLoading,
    // Send waits only while nothing of the routed chat is on screen.
    historyPending: chatLoading && (messages.length === 0 || chatId !== (routeChatId ?? null)),
    hasMoreOlder,
    loadingOlder: paging.loadingOlder,
    loadOlderMessages: paging.loadOlderMessages,
    newerPage: paging.newerPage,
    jumpToLatest: paging.jumpToLatest,
    highlightedMessageId,
    handleFirstReply,
    startNewChat,
    awaitTitle,
  };
}

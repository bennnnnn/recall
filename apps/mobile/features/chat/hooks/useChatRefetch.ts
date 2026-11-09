import { useCallback, useEffect, useRef, type Dispatch, type MutableRefObject, type RefObject, type SetStateAction } from "react";
import type { AppStateStatus } from "react-native";

import { api, type Chat, type Message } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { reportFailure } from "@/lib/sentry";
import { onAppStateChange } from "@/lib/foregroundRefresh";
import { getCachedChat, getFetchedChat } from "@/features/chat/model/chatListCache";
import { shouldForceForegroundChatRecovery, shouldRefetchChatOnForeground } from "@/features/chat/model/foregroundRefetch";
import { markCachedChatPagesStale, shouldSkipChatPageRead } from "@/features/chat/model/messageCache";
import { mergeLocalAttachmentUris } from "@/features/chat/model/messageMerge";
import { MESSAGE_PAGE_SIZE } from "@/features/chat/model/constants";
import { getChatMutationRevision } from "@/features/chat/drawer/drawer";
import type { EditThread } from "@/features/chat/model/threadEdit";

/** `silentRefetchChat`: the open chat's newest page, merged into the thread without a spinner. */
type Refetch = (openChatId: string, cancelled: () => boolean, opts?: { force?: boolean }) => Promise<void>;

type RefetchOptions = {
  token: string | null;
  /** The route loader's view: a read that finishes after it moved on is dropped. */
  viewRef: MutableRefObject<{ version: number }>;
  activeChatRef: RefObject<string | null>;
  messagesRef: RefObject<Message[]>;
  setChatId: Dispatch<SetStateAction<string | null>>;
  editThread: EditThread;
  setHasMoreOlder: Dispatch<SetStateAction<boolean>>;
  applyMetadata: (chat: Chat | undefined) => void;
  notePageRead: (chatId: string) => void;
  /** A reply streams or a picture is being made: its own end brings the page. */
  turnBusy: () => boolean;
  /** The thread is a window around a search hit, not the newest page. */
  hasMoreNewer: boolean;
};

/**
 * Reads the open chat's newest page and merges it into the thread, unless it was read within
 * the stale window (`force` reads it anyway). The thread on screen stays as it is when the
 * read fails, or when anything changed it while the read was out.
 */
export function useSilentRefetchChat({
  token, viewRef, activeChatRef, messagesRef, setChatId, editThread, setHasMoreOlder, applyMetadata, notePageRead,
  turnBusy, hasMoreNewer,
}: RefetchOptions): Refetch {
  const session = getSessionGeneration();
  return useCallback(
    async (openChatId, cancelled, opts) => {
      if (!token || session !== getSessionGeneration() || openChatId !== activeChatRef.current || hasMoreNewer) return;
      const version = viewRef.current.version;
      const ownerSession = getSessionGeneration();
      const previousMessages = messagesRef.current;
      const stale = () =>
        cancelled() || ownerSession !== getSessionGeneration() || version !== viewRef.current.version ||
        turnBusy() || messagesRef.current !== previousMessages;
      if (await shouldSkipChatPageRead(openChatId, opts?.force)) return;
      if (stale()) return;
      try {
        const revision = getChatMutationRevision(openChatId);
        const [chat, page] = await Promise.all([
          getFetchedChat(openChatId) ?? api.getChat(token, openChatId),
          api.listMessages(token, openChatId, { limit: MESSAGE_PAGE_SIZE }),
        ]);
        if (stale()) return;
        setChatId(chat.id);
        applyMetadata(revision === getChatMutationRevision(openChatId) ? chat : getCachedChat(openChatId));
        editThread((prev) => mergeLocalAttachmentUris(prev, page.messages), "page_refresh");
        setHasMoreOlder(page.has_more);
        notePageRead(openChatId);
      } catch (error) {
        reportFailure("chat_refresh", error); // The messages on screen stay.
      }
    },
    [
      token, session, viewRef, activeChatRef, messagesRef, setChatId, editThread, setHasMoreOlder, applyMetadata,
      notePageRead, turnBusy, hasMoreNewer,
    ],
  );
}

type ForegroundOptions = {
  token: string | null;
  chatId: string | null;
  routeChatId: string | undefined;
  // AppState closures must read the latest flags: deps alone would leave a stale "still
  // streaming" view after ws.onclose commits a partial reply.
  streamingRef: RefObject<boolean>;
  chatLoadingRef: RefObject<boolean>;
  imageGeneratingRef?: RefObject<boolean>;
  refetch: Refetch;
};

/**
 * A return from the background reads the open chat again: another device may have written to
 * it, and a reply cut off when the app left is read past the stale window. The listener
 * follows the chat and the account; a new message never subscribes it again.
 */
export function useForegroundRefetch({
  token, chatId, routeChatId, streamingRef, chatLoadingRef, imageGeneratingRef, refetch,
}: ForegroundOptions): void {
  const session = getSessionGeneration();
  const wasStreamingWhenBackgroundedRef = useRef(false);
  useEffect(() => {
    let cancelled = false;
    const onAppState = (state: AppStateStatus, returned: boolean) => {
      if (session !== getSessionGeneration()) return;
      if (state === "background" || state === "inactive") {
        // Another device may write to any chat while this one is away.
        if (state === "background") markCachedChatPagesStale();
        if (streamingRef.current || Boolean(imageGeneratingRef?.current)) {
          wasStreamingWhenBackgroundedRef.current = true;
        }
        // An unused draft is dropped by useDraftChat, once, on background.
        return;
      }
      // An iOS "inactive" blip (Control Centre, a prompt) left the socket and the page as they were.
      if (!returned) return;
      // Backgrounding mid-stream kills the socket; onclose commits a truncated
      // bubble. When we return to foreground with streaming finished, pull the
      // server's full reply without requiring the user to leave the chat.
      const openChatId = routeChatId ?? chatId;
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
      void refetch(openChatId, () => cancelled, { force });
    };
    const stopAppState = onAppStateChange(onAppState);
    return () => {
      cancelled = true;
      stopAppState();
    };
  }, [chatId, routeChatId, token, refetch, session, imageGeneratingRef, chatLoadingRef, streamingRef]);
}

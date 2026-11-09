import { useEffect, useRef, type Dispatch, type MutableRefObject, type RefObject, type SetStateAction } from "react";

import type { IconName } from "@/ui/icons/names";

import { useComposerDraftApiOptional } from "@/features/chat/context/ComposerDraftContext";
import { api, type Chat, type Message } from "@/lib/api";
import { ApiRequestError } from "@/lib/api/client";
import { getSessionGeneration } from "@/lib/auth";
import { reportFailure } from "@/lib/sentry";
import { getCachedChat, getFetchedChat } from "@/features/chat/model/chatListCache";
import {
  cachedChatPageFetchedAt,
  clearCachedChatMessages,
  isCachedChatPageFresh,
  peekCachedChatPage,
  readCachedChatMessages,
  type CachedChatPage,
} from "@/features/chat/model/messageCache";
import { addedSincePaint, mergeOpenedPage, paintCachedThread } from "@/features/chat/model/messageMerge";
import { MESSAGE_PAGE_SIZE } from "@/features/chat/model/constants";
import { beginOpenedPageRead, type OpenedPageRead } from "@/features/chat/model/openedPage";
import { chatHasThreadContent, shouldProbePreviousChat } from "@/features/chat/model/draftLogic";
import { getChatMutationRevision, removeChatGlobal } from "@/features/chat/drawer/drawer";
import type { useDraftChat } from "@/features/chat/hooks/useDraftChat";
import type { EditThread } from "@/features/chat/model/threadEdit";

type Composer = ReturnType<typeof useComposerDraftApiOptional>;

type Options = {
  token: string | null;
  routeChatId: string | undefined;
  /** The route loader's view: a read that finishes after it moved on is dropped. */
  viewRef: MutableRefObject<{ version: number }>;
  draft: Pick<
    ReturnType<typeof useDraftChat>,
    "draftChatIdRef" | "skipLoadForChatIdRef" | "creatingRef" | "discardEmptyChat" | "clearDraftChat"
  >;
  messagesRef: RefObject<Message[]>;
  setChatId: Dispatch<SetStateAction<string | null>>;
  setChatLoading: Dispatch<SetStateAction<boolean>>;
  setHasMoreOlder: Dispatch<SetStateAction<boolean>>;
  editThread: EditThread;
  applyMetadata: (chat: Chat | undefined) => void;
  resetMetadata: () => void;
  /** No chat on screen: the thread, its title and flags, as New chat leaves them. */
  clearView: () => void;
  notePageRead: (chatId: string, fetchedAt?: number) => void;
  notePageUnmerged: (chatId: string) => void;
  clearPageSync: () => void;
  resetPaging: () => void;
  pollForTitle: (token: string, chatId: string) => unknown;
  startNewChat: (opts?: { force?: boolean }) => void;
  showActionBanner: (message: string, icon?: IconName) => void;
  t: (key: string) => string;
};

/** One open of the routed chat, for the steps below: each set is guarded by `isCurrent`. */
type Open = { options: Options; chatId: string; token: string; isCurrent: () => boolean };

/**
 * Opens the chat the route names, once per route and account: the chat this view just made
 * as it is, a page kept moments ago at once, any other from the cached page and then the
 * server's. A rotated token or a recreated callback does not open it again.
 */
export function useChatRouteOpen(options: Options): void {
  const { token, routeChatId } = options;
  const composer = useComposerDraftApiOptional();
  const session = getSessionGeneration();
  const signedIn = Boolean(token);
  const priorRouteChatIdRef = useRef<string | null>(null);
  useEffect(() => {
    const { viewRef, draft, messagesRef } = options;
    options.resetPaging();
    options.clearPageSync();
    if (!token) {
      options.setChatLoading(false);
      return;
    }
    const openChatId = routeChatId ?? null;
    const prevOpenChatId = priorRouteChatIdRef.current;
    if (prevOpenChatId && prevOpenChatId !== openChatId) {
      if (
        shouldProbePreviousChat({
          chatId: prevOpenChatId,
          messagesHadAssistant: chatHasThreadContent(messagesRef.current),
        })
      ) {
        draft.discardEmptyChat(prevOpenChatId);
      }
    }
    if (openChatId && draft.draftChatIdRef.current) {
      draft.clearDraftChat();
    }
    priorRouteChatIdRef.current = openChatId;

    let cancelled = false;
    let opened: OpenedPageRead | null = null;
    const version = viewRef.current.version;
    const isCurrent = () => !cancelled && session === getSessionGeneration() && version === viewRef.current.version;
    void (async () => {
      if (!openChatId) {
        options.setChatLoading(false);
        if (!draft.creatingRef.current) options.clearView();
        return;
      }
      const open: Open = { options, chatId: openChatId, token, isCurrent };
      if (openCreatedChat(open)) return;
      const kept = peekCachedChatPage(openChatId);
      if (openKeptPage(open, kept)) return;
      options.setChatLoading(true);
      options.setHasMoreOlder(false);
      // Send works once the cached page is painted; a turn sent before the page lands waits for it.
      const read = beginOpenedPageRead(openChatId);
      opened = read;
      await readOpenedChat(open, read, kept, composer);
    })();
    return () => {
      cancelled = true;
      // Left before the page landed: a turn waiting for it goes back to this chat's composer (not past sign-out).
      opened?.cancel(session === getSessionGeneration() ? composer : null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload for a new route chat or account, not a rotated token or a recreated callback
  }, [signedIn, session, routeChatId]);
}

/** Paints a cached page (none: an empty thread) under the chat's drawer row, if it has one. */
function showCachedPage(
  { options, chatId }: Open,
  cached: CachedChatPage | null,
  listed = getCachedChat(chatId),
): void {
  options.setChatId(chatId);
  options.editThread((prev) => paintCachedThread(prev, cached?.messages ?? []), "cached_paint");
  options.resetMetadata();
  if (cached) {
    options.setHasMoreOlder(cached.has_more);
    if (listed) options.applyMetadata(listed);
  }
}

/** The chat this view just made: it holds what it shows, so it opens without a read. True when it was. */
function openCreatedChat({ options, chatId }: Open): boolean {
  const { skipLoadForChatIdRef } = options.draft;
  if (skipLoadForChatIdRef.current !== chatId) return false;
  skipLoadForChatIdRef.current = null;
  options.setChatId(chatId);
  options.setChatLoading(false);
  // The chat this view just created holds nothing but what it shows.
  options.notePageRead(chatId);
  return true;
}

/** A page this device kept moments ago, shown without a read while its row says nothing moved. */
function openKeptPage(open: Open, kept: CachedChatPage | null): boolean {
  const { options, chatId, token } = open;
  const listed = getFetchedChat(chatId);
  if (!kept || !listed || !isCachedChatPageFresh(chatId, listed.updated_at)) return false;
  // This device wrote the page moments ago and nothing suggests the chat moved on.
  showCachedPage(open, kept, listed);
  options.notePageRead(chatId, cachedChatPageFetchedAt(kept) ?? Date.now());
  options.setChatLoading(false);
  if (!listed.title && kept.messages.length > 0) options.pollForTitle(token, chatId);
  return true;
}

/** Paints the cached page, then merges the server's page and the chat's row once both land. */
async function readOpenedChat(
  open: Open,
  read: OpenedPageRead,
  kept: CachedChatPage | null,
  composer: Composer,
): Promise<void> {
  const { options, chatId, token, isCurrent } = open;
  try {
    // Stale-while-revalidate: keep the previous thread painted during the
    // (fast) cache read, then swap in one shot — no blank flash on open.
    // The old thread's pending work still cannot paint into this route
    // because every set below is guarded by isCurrent().
    const cached = kept ?? await readCachedChatMessages(chatId);
    if (!isCurrent()) return;
    showCachedPage(open, cached);
    const painted = new Set(cached?.messages.map((m) => m.id));
    const revision = getChatMutationRevision(chatId);
    const [chat, page] = await Promise.all([
      getFetchedChat(chatId) ?? api.getChat(token, chatId),
      api.listMessages(token, chatId, { limit: MESSAGE_PAGE_SIZE }),
    ]);
    if (!isCurrent()) return;
    options.setChatId(chat.id);
    const currentChat = revision === getChatMutationRevision(chatId) ? chat : getCachedChat(chatId);
    options.applyMetadata(currentChat);
    // A turn that went out before the page may be in it: merge once nothing of it is on screen, else reread later.
    if (read.release() || !addedSincePaint(options.messagesRef.current, page.messages, painted)) {
      options.editThread((prev) => mergeOpenedPage(prev, page.messages, painted), "opened_page");
      options.setHasMoreOlder(page.has_more);
      options.notePageRead(chatId);
    } else options.notePageUnmerged(chatId);
    if (currentChat && !currentChat.title && page.messages.length > 0) {
      options.pollForTitle(token, chatId);
    }
  } catch (error) {
    if (isCurrent()) {
      if (error instanceof ApiRequestError && error.status === 404) {
        read.chatGone(composer);
        removeChatGlobal(chatId);
        void clearCachedChatMessages(chatId);
        options.startNewChat({ force: true });
      } else reportFailure("chat_load", error);
      options.showActionBanner(options.t("common.error"), "alert-circle");
    }
  } finally {
    // A read that failed lets a turn waiting for it go out.
    if (isCurrent()) read.release();
    if (isCurrent()) options.setChatLoading(false);
  }
}

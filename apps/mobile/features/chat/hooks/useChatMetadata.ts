import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

import type { Chat } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { useLatestRef } from "@/lib/latestRef";
import { subscribeChatChanges } from "@/features/chat/drawer/drawer";
import { getCachedChatList, getFetchedChat, subscribeChatList } from "@/features/chat/model/chatListCache";

/**
 * The open chat's row as the server last sent it this session (`getFetchedChat`), read again
 * only when the list changes: the list is read on every open of the drawer, so it is many
 * renders' answer.
 */
function useListedChat(chatId: string | null): Chat | undefined {
  const memo = useRef<{ list: unknown; chatId: string | null; chat: Chat | undefined } | null>(null);
  const read = useCallback(() => {
    const list = getCachedChatList();
    if (memo.current && memo.current.list === list && memo.current.chatId === chatId) return memo.current.chat;
    const chat = chatId ? getFetchedChat(chatId) : undefined;
    memo.current = { list, chatId, chat };
    return chat;
  }, [chatId]);
  return useSyncExternalStore(subscribeChatList, read, read);
}

/**
 * The open chat's title, pin and archive flags, as its header and menu show them. The drawer's
 * list is their one source while it holds the chat: a rename or archive on another device
 * comes with its next read, and the header follows (pre-launch review, 2026-11-27: a copy of
 * its own kept the old title and flags). The state here is the fallback for a chat the list
 * does not hold (not read yet, or past its pages) and for a title the list does not have yet.
 * A change made in the drawer lands at once; opening a chat sets them from its row
 * (`applyMetadata`), and leaving it puts them back (`resetMetadata`).
 */
export function useChatMetadata(chatId: string | null) {
  const [ownTitle, setChatTitle] = useState<string | null>(null);
  const [ownPinned, setPinned] = useState(false);
  const [ownArchived, setArchived] = useState(false);
  const session = getSessionGeneration();
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
  const resetMetadata = useCallback(() => {
    setChatTitle(null);
    setPinned(false);
    setArchived(false);
  }, []);

  const listed = useListedChat(chatId);
  // The row's news is kept as the hook's own too: a list dropped meanwhile (Settings' archived
  // chats) fell back to the title before a rename made on another device.
  useEffect(() => {
    if (!listed) return;
    if (listed.title?.trim()) setChatTitle(listed.title);
    setPinned(listed.pinned);
    setArchived(Boolean(listed.archived));
  }, [listed]);
  const chatTitle = listed?.title?.trim() ? listed.title : ownTitle;
  const pinned = listed ? listed.pinned : ownPinned;
  const archived = listed ? Boolean(listed.archived) : ownArchived;

  return { chatTitle, setChatTitle, pinned, setPinned, archived, setArchived, applyMetadata, resetMetadata };
}

export type ChatMetadata = ReturnType<typeof useChatMetadata>;

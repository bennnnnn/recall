import { useCallback, useEffect, useState } from "react";

import type { Chat } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { useLatestRef } from "@/lib/latestRef";
import { subscribeChatChanges } from "@/features/chat/drawer/drawer";

/**
 * The open chat's title, pin and archive flags, as its header and menu show them. A change
 * made in the drawer (a rename, a pin) lands at once; opening a chat sets them from its row
 * (`applyMetadata`), and leaving it puts them back (`resetMetadata`).
 */
export function useChatMetadata(chatId: string | null) {
  const [chatTitle, setChatTitle] = useState<string | null>(null);
  const [pinned, setPinned] = useState(false);
  const [archived, setArchived] = useState(false);
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

  return { chatTitle, setChatTitle, pinned, setPinned, archived, setArchived, applyMetadata, resetMetadata };
}

export type ChatMetadata = ReturnType<typeof useChatMetadata>;

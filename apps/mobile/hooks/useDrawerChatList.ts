import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { CHAT_LIST_STALE_MS } from "@/components/drawer/conversationListStyles";
import {
  activeChatsFromGroups,
  ARCHIVED_CHAT_SECTION,
  CHAT_DATE_SECTIONS,
  defaultChatSectionCollapsed,
  isCollapsibleChatSection,
  patchChatListGroups,
  removeChatFromGroups,
  type ChatListSectionKey,
} from "@/lib/chatListSections";
import {
  registerChatArchiveMover,
  registerChatInserter,
  registerChatPatcher,
  subscribeChatTitleGenerating,
} from "@/lib/drawer";
import { emptyChatList, insertChatIntoGroups } from "@/lib/drawerChatList";
import { api, Chat, ChatList } from "@/lib/api";
import { scheduleIdleTask } from "@/lib/scheduleIdle";

type Params = {
  token: string | null;
  isDrawerOpen: boolean;
};

export function useDrawerChatList({ token, isDrawerOpen }: Params) {
  const [loading, setLoading] = useState(true);
  const [groups, setGroups] = useState<ChatList>(emptyChatList);
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {};
    for (const key of [...CHAT_DATE_SECTIONS, ARCHIVED_CHAT_SECTION]) {
      if (defaultChatSectionCollapsed(key)) {
        initial[key] = true;
      }
    }
    return initial;
  });
  const [error, setError] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const lastFetchedRef = useRef(0);
  const [, setTitlePendingTick] = useState(0);

  const allChats = useMemo(() => activeChatsFromGroups(groups), [groups]);

  const isSectionCollapsed = useCallback(
    (key: ChatListSectionKey) =>
      isCollapsibleChatSection(key) &&
      (collapsedSections[key] ?? defaultChatSectionCollapsed(key)),
    [collapsedSections],
  );

  const toggleSectionCollapsed = useCallback((key: ChatListSectionKey) => {
    if (!isCollapsibleChatSection(key)) return;
    setCollapsedSections((prev) => ({
      ...prev,
      [key]: !(prev[key] ?? defaultChatSectionCollapsed(key)),
    }));
  }, []);

  const load = useCallback(
    async (background = false) => {
      if (!token) {
        setLoading(false);
        return;
      }
      if (!background) {
        setLoading(true);
      }
      setError(false);
      try {
        const chatGroups = await api.listChats(token);
        setGroups({
          pinned: chatGroups.pinned,
          today: chatGroups.today,
          yesterday: chatGroups.yesterday,
          last_7_days: chatGroups.last_7_days,
          this_month: chatGroups.this_month,
          older: chatGroups.older,
          archived: chatGroups.archived ?? [],
        });
        lastFetchedRef.current = Date.now();
      } catch {
        if (!background) setError(true);
      } finally {
        if (!background) {
          setLoading(false);
        }
      }
    },
    [token],
  );

  const handleRefresh = useCallback(async () => {
    if (!token) return;
    setRefreshing(true);
    try {
      await load(false);
    } finally {
      setRefreshing(false);
    }
  }, [token, load]);

  useEffect(() => {
    load(false);
  }, [load]);

  useEffect(() => {
    if (!isDrawerOpen) return;
    const stale =
      Date.now() - lastFetchedRef.current > CHAT_LIST_STALE_MS ||
      allChats.length === 0;
    if (!stale) return;

    let cancelled = false;
    const cancelIdle = scheduleIdleTask(() => {
      if (!cancelled) void load(true);
    });
    return () => {
      cancelled = true;
      cancelIdle();
    };
  }, [isDrawerOpen, load, allChats.length]);

  const patchChatInGroups = useCallback((chatId: string, patch: Partial<Chat>) => {
    setGroups((prev) => patchChatListGroups(prev, chatId, patch));
  }, []);

  const insertChatInGroups = useCallback((chat: Chat) => {
    setGroups((prev) => insertChatIntoGroups(prev, chat));
  }, []);

  useEffect(() => {
    registerChatPatcher(patchChatInGroups);
    return () => registerChatPatcher(null);
  }, [patchChatInGroups]);

  useEffect(() => {
    registerChatInserter(insertChatInGroups);
    return () => registerChatInserter(null);
  }, [insertChatInGroups]);

  useEffect(() => {
    return subscribeChatTitleGenerating(() => setTitlePendingTick((n) => n + 1));
  }, []);

  const moveChatPinState = useCallback((chatId: string, pinned: boolean) => {
    setGroups((prev) => {
      const chat = [...activeChatsFromGroups(prev), ...prev.archived].find(
        (c) => c.id === chatId,
      );
      if (!chat) return prev;
      const updated = { ...chat, pinned };
      const rest = removeChatFromGroups(prev, chatId);
      if (pinned) {
        return { ...rest, pinned: [updated, ...rest.pinned] };
      }
      return { ...rest, today: [updated, ...rest.today] };
    });
  }, []);

  const moveChatArchiveState = useCallback((chatId: string, archived: boolean) => {
    setGroups((prev) => {
      const chat = [...activeChatsFromGroups(prev), ...prev.archived].find(
        (c) => c.id === chatId,
      );
      if (!chat) return prev;
      const updated = { ...chat, archived };
      const rest = removeChatFromGroups(prev, chatId);
      return insertChatIntoGroups(rest, updated);
    });
  }, []);

  useEffect(() => {
    registerChatArchiveMover(moveChatArchiveState);
    return () => registerChatArchiveMover(null);
  }, [moveChatArchiveState]);

  const removeChatFromGroupsById = useCallback((chatId: string) => {
    setGroups((prev) => removeChatFromGroups(prev, chatId));
  }, []);

  return {
    loading,
    error,
    refreshing,
    groups,
    allChats,
    load,
    handleRefresh,
    patchChatInGroups,
    insertChatInGroups,
    isSectionCollapsed,
    toggleSectionCollapsed,
    moveChatPinState,
    moveChatArchiveState,
    removeChatFromGroupsById,
  };
}

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

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
  fetchChatList,
  getCachedChatList,
  getChatListFetchedAt,
  isChatListFresh,
  setChatListCache,
} from "@/lib/chatListCache";
import {
  registerChatArchiveMover,
  registerChatInserter,
  registerChatPatcher,
  registerChatRemover,
  subscribeChatTitleGenerating,
} from "@/lib/drawer";
import {
  CHAT_LIST_STALE_MS,
  drawerChatFetchMode,
  emptyChatList,
  insertChatIntoGroups,
} from "@/lib/drawerChatList";
import { Chat, ChatList } from "@/lib/api";
import { scheduleIdleTask } from "@/lib/scheduleIdle";

type Params = {
  token: string | null;
  isDrawerOpen: boolean;
};

function applyChatList(
  data: ChatList,
  setGroups: (groups: ChatList) => void,
  lastFetchedRef: { current: number },
  hasLoadedOnceRef: { current: boolean },
  fetchedAt?: number,
) {
  setGroups(data);
  lastFetchedRef.current = fetchedAt ?? getChatListFetchedAt() ?? Date.now();
  hasLoadedOnceRef.current = true;
}

export function useDrawerChatList({ token, isDrawerOpen }: Params) {
  // Idle until the drawer opens — ConversationList mounts with the chat
  // screen, so an eager true would spin before the user ever opens history.
  const [loading, setLoading] = useState(false);
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
  const hasLoadedOnceRef = useRef(false);
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

  const hydrateFromCache = useCallback(() => {
    const cached = getCachedChatList();
    const fetchedAt = getChatListFetchedAt();
    if (!cached || fetchedAt == null) return false;
    if (hasLoadedOnceRef.current && fetchedAt <= lastFetchedRef.current) {
      return true;
    }
    applyChatList(cached, setGroups, lastFetchedRef, hasLoadedOnceRef, fetchedAt);
    return true;
  }, []);

  const load = useCallback(
    async (background = false, force = false) => {
      if (!token) {
        setLoading(false);
        return;
      }
      if (!background && !force && isChatListFresh() && hydrateFromCache()) {
        return;
      }
      if (!background) {
        setLoading(true);
      }
      setError(false);
      try {
        // Blocking paths force a network read; background respects TTL/inflight.
        const chatGroups = await fetchChatList(token, {
          force: force || !background,
        });
        if (!chatGroups) {
          if (!background) setError(true);
          return;
        }
        applyChatList(chatGroups, setGroups, lastFetchedRef, hasLoadedOnceRef);
      } catch {
        if (!background) setError(true);
      } finally {
        if (!background) {
          setLoading(false);
        }
      }
    },
    [token, hydrateFromCache],
  );

  const handleRefresh = useCallback(async () => {
    if (!token) return;
    setRefreshing(true);
    try {
      await load(false, true);
    } finally {
      setRefreshing(false);
    }
  }, [token, load]);

  // Idle-warm GET /chats while the drawer is closed so first open has titles.
  useEffect(() => {
    if (!token || isDrawerOpen) return;

    hydrateFromCache();

    let cancelled = false;
    const cancelIdle = scheduleIdleTask(() => {
      if (cancelled) return;
      void (async () => {
        const data = await fetchChatList(token);
        if (cancelled || !data) return;
        applyChatList(data, setGroups, lastFetchedRef, hasLoadedOnceRef);
      })();
    });
    return () => {
      cancelled = true;
      cancelIdle();
    };
  }, [token, isDrawerOpen, hydrateFromCache]);

  useEffect(() => {
    // Prefetch may have filled the module cache; sync into hook state before
    // deciding whether a spinner full-fetch is needed.
    hydrateFromCache();

    const mode = drawerChatFetchMode({
      isDrawerOpen,
      hasToken: Boolean(token),
      hasLoadedOnce: hasLoadedOnceRef.current,
      lastFetchedAt: lastFetchedRef.current,
      chatCount: allChats.length,
      now: Date.now(),
      staleMs: CHAT_LIST_STALE_MS,
    });
    if (mode === "skip") return;
    if (mode === "full") {
      void load(false);
      return;
    }

    let cancelled = false;
    const cancelIdle = scheduleIdleTask(() => {
      if (!cancelled) void load(true);
    });
    return () => {
      cancelled = true;
      cancelIdle();
    };
  }, [isDrawerOpen, token, load, allChats.length, hydrateFromCache]);

  const patchChatInGroups = useCallback((chatId: string, patch: Partial<Chat>) => {
    setGroups((prev) => {
      const next = patchChatListGroups(prev, chatId, patch);
      setChatListCache(next);
      return next;
    });
  }, []);

  const insertChatInGroups = useCallback((chat: Chat) => {
    setGroups((prev) => {
      const next = insertChatIntoGroups(prev, chat);
      setChatListCache(next);
      return next;
    });
  }, []);

  useEffect(() => {
    registerChatPatcher(patchChatInGroups);
    return () => registerChatPatcher(null);
  }, [patchChatInGroups]);

  useEffect(() => {
    registerChatInserter(insertChatInGroups);
    return () => registerChatInserter(null);
  }, [insertChatInGroups]);

  const removeChatFromGroupsById = useCallback((chatId: string) => {
    setGroups((prev) => {
      const next = removeChatFromGroups(prev, chatId);
      setChatListCache(next);
      return next;
    });
  }, []);

  useEffect(() => {
    registerChatRemover(removeChatFromGroupsById);
    return () => registerChatRemover(null);
  }, [removeChatFromGroupsById]);

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
      const next = pinned
        ? { ...rest, pinned: [updated, ...rest.pinned] }
        : { ...rest, today: [updated, ...rest.today] };
      setChatListCache(next);
      return next;
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
      const next = insertChatIntoGroups(rest, updated);
      setChatListCache(next);
      return next;
    });
  }, []);

  useEffect(() => {
    registerChatArchiveMover(moveChatArchiveState);
    return () => registerChatArchiveMover(null);
  }, [moveChatArchiveState]);

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

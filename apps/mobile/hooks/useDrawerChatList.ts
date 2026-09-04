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
} from "@/lib/chat/chatListSections";
import {
  fetchChatList,
  getCachedChatList,
  getChatListFetchedAt,
  isChatListFresh,
  updateChatListCache,
} from "@/lib/cache/chatListCache";
import {
  publishChatChange,
  registerChatArchiveMover,
  registerChatInserter,
  registerChatPatcher,
  registerChatRemover,
  subscribeChatTitleGenerating,
} from "@/lib/drawer";
import {
  drawerChatFetchMode,
  emptyChatList,
  insertChatIntoGroups,
  shouldWarmClosedDrawerChatList,
} from "@/lib/drawerChatList";
import { Chat, ChatList } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { scheduleIdleTask } from "@/lib/scheduleIdle";

type Params = { token: string | null; isDrawerOpen: boolean };

function initialCollapsedSections(): Record<string, boolean> {
  return Object.fromEntries([...CHAT_DATE_SECTIONS, ARCHIVED_CHAT_SECTION]
    .map((key) => [key, defaultChatSectionCollapsed(key)]));
}

export function useDrawerChatList({ token, isDrawerOpen }: Params) {
  const session = getSessionGeneration();
  const [snapshot, setSnapshot] = useState(() => ({ session, groups: emptyChatList() }));
  const groups = useMemo(() => snapshot.session === session && token ? snapshot.groups : emptyChatList(), [snapshot, session, token]);
  const [loading, setLoading] = useState(false);
  const [collapsedSections, setCollapsedSections] = useState(initialCollapsedSections);
  const [error, setError] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const hasLoadedOnceRef = useRef(false);
  const ownerRef = useRef(session);
  const mountedRef = useRef(true);
  const loadIdRef = useRef(0);
  const [, setTitlePendingTick] = useState(0);
  if (ownerRef.current !== session) {
    ownerRef.current = session;
    hasLoadedOnceRef.current = false;
    loadIdRef.current++;
  }
  const current = useCallback(() => mountedRef.current && session === getSessionGeneration(), [session]);
  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);
  useEffect(() => {
    setLoading(false);
    setRefreshing(false);
    setError(false);
    setCollapsedSections(initialCollapsedSections());
  }, [session]);

  const allChats = useMemo(() => activeChatsFromGroups(groups), [groups]);
  const isSectionCollapsed = useCallback((key: ChatListSectionKey) =>
    isCollapsibleChatSection(key) && (collapsedSections[key] ?? defaultChatSectionCollapsed(key)), [collapsedSections]);
  const toggleSectionCollapsed = useCallback((key: ChatListSectionKey) => {
    if (!isCollapsibleChatSection(key)) return;
    setCollapsedSections((prev) => ({ ...prev, [key]: !(prev[key] ?? defaultChatSectionCollapsed(key)) }));
  }, []);

  const applyChatList = useCallback((data: ChatList, fetched = true) => {
    if (!current()) return;
    setSnapshot((prev) => prev.session === session && prev.groups === data ? prev : { session, groups: data });
    if (fetched) hasLoadedOnceRef.current = true;
  }, [current, session]);
  const hydrateFromCache = useCallback(() => {
    if (!token || !current()) return false;
    const cached = getCachedChatList();
    if (!cached) return false;
    const fetched = getChatListFetchedAt() != null;
    applyChatList(cached, fetched);
    return fetched;
  }, [token, current, applyChatList]);

  const load = useCallback(async (background = false, force = false) => {
    if (!token || !current()) return;
    if (!force && isChatListFresh() && hydrateFromCache()) return;
    const loadId = ++loadIdRef.current;
    if (!background) setLoading(true);
    setError(false);
    const data = await fetchChatList(token, { force });
    if (!current() || loadId !== loadIdRef.current) return;
    if (data) applyChatList(getCachedChatList() ?? data);
    else if (!background) setError(true);
    if (!background) setLoading(false);
  }, [token, current, hydrateFromCache, applyChatList]);

  const handleRefresh = useCallback(async () => {
    if (!token || !current()) return;
    setRefreshing(true);
    try { await load(false, true); }
    finally { if (current()) setRefreshing(false); }
  }, [token, current, load]);

  // Idle warm is only for first paint. Closing the drawer never triggers a read.
  useEffect(() => {
    hydrateFromCache();
    if (!shouldWarmClosedDrawerChatList({ hasToken: Boolean(token), isDrawerOpen, hasLoadedOnce: hasLoadedOnceRef.current })) return;
    if (!token) return;
    let cancelled = false;
    const cancelIdle = scheduleIdleTask(() => {
      if (cancelled || !current()) return;
      void fetchChatList(token).then((data) => {
        if (!cancelled && current() && data) applyChatList(getCachedChatList() ?? data);
      });
    });
    return () => { cancelled = true; cancelIdle(); };
  }, [token, isDrawerOpen, current, hydrateFromCache, applyChatList]);

  useEffect(() => {
    hydrateFromCache();
    if (drawerChatFetchMode({ isDrawerOpen, hasToken: Boolean(token), hasLoadedOnce: hasLoadedOnceRef.current }) !== "skip") void load();
  }, [isDrawerOpen, token, load, hydrateFromCache]);

  const updateGroups = useCallback((chatId: string, patch: Partial<Chat> | null, update: (previous: ChatList) => ChatList) => {
    if (!token || !current()) return;
    applyChatList(updateChatListCache(update), false);
    publishChatChange(chatId, patch);
  }, [token, current, applyChatList]);
  const patchChatInGroups = useCallback((chatId: string, patch: Partial<Chat>) => {
    const normalized = patch.archived === true ? { ...patch, pinned: false } : patch;
    updateGroups(chatId, normalized, (prev) => patchChatListGroups(prev, chatId, normalized));
  }, [updateGroups]);
  const insertChatInGroups = useCallback((chat: Chat) => {
    updateGroups(chat.id, chat, (prev) => insertChatIntoGroups(prev, chat));
  }, [updateGroups]);
  const removeChatFromGroupsById = useCallback((chatId: string) => {
    updateGroups(chatId, null, (prev) => removeChatFromGroups(prev, chatId));
  }, [updateGroups]);
  const moveChatPinState = useCallback((chatId: string, pinned: boolean) => {
    patchChatInGroups(chatId, { pinned });
  }, [patchChatInGroups]);
  const moveChatArchiveState = useCallback((chatId: string, archived: boolean) => {
    patchChatInGroups(chatId, archived ? { archived, pinned: false } : { archived });
  }, [patchChatInGroups]);

  useEffect(() => {
    registerChatPatcher(patchChatInGroups);
    registerChatInserter(insertChatInGroups);
    registerChatRemover(removeChatFromGroupsById);
    registerChatArchiveMover(moveChatArchiveState);
    return () => {
      registerChatPatcher(null);
      registerChatInserter(null);
      registerChatRemover(null);
      registerChatArchiveMover(null);
    };
  }, [patchChatInGroups, insertChatInGroups, removeChatFromGroupsById, moveChatArchiveState]);
  useEffect(() => subscribeChatTitleGenerating(() => setTitlePendingTick((n) => n + 1)), []);

  return {
    loading, error, refreshing, groups, allChats, load, handleRefresh,
    patchChatInGroups, insertChatInGroups, isSectionCollapsed, toggleSectionCollapsed,
    moveChatPinState, moveChatArchiveState, removeChatFromGroupsById,
  };
}

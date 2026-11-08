import { useAccountSession } from "@/contexts/accountSession";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type RefObject } from "react";

import {
  activeChatsFromGroups,
  ARCHIVED_CHAT_SECTION,
  CHAT_DATE_SECTIONS,
  defaultChatSectionCollapsed,
  isCollapsibleChatSection,
  patchChatListGroups,
  removeChatFromGroups,
  type ChatListSectionKey,
} from "@/features/chat/model/listSections";
import {
  chatListRowsRemoved,
  fetchChatList,
  fetchMoreArchivedChats,
  fetchOlderChats,
  getCachedChatList,
  getChatListFetchedAt,
  isChatListDropped,
  isChatListFresh,
  regroupCachedChatList,
  restoreChatList,
  subscribeChatList,
  updateChatListCache,
} from "@/features/chat/model/chatListCache";
import {
  publishChatChange,
  registerChatInserter,
  registerChatPatcher,
  registerChatRemover,
  subscribeChatTitleGenerating,
} from "@/features/chat/drawer/drawer";
import {
  drawerChatFetchMode,
  emptyChatList,
  insertChatIntoGroups,
  shouldWarmClosedDrawerChatList,
} from "@/features/chat/drawer/drawerChatList";
import { Chat, ChatList } from "@/lib/api";
import { onAppEvent } from "@/lib/appEvents";
import { getSessionGeneration } from "@/lib/auth";
import { isExpectedReadFailure, type ResourceUpdate } from "@/lib/cache/sessionResource";
import { scheduleIdleTask } from "@/lib/scheduleIdle";
import { useReadFailureReport } from "@/hooks/useReadFailureReport";
import { useReconnectRefresh } from "@/hooks/useReconnectRefresh";
import { useLatestRef } from "@/lib/latestRef";

type Params = { isDrawerOpen: boolean };

function initialCollapsedSections(): Record<string, boolean> {
  return Object.fromEntries([...CHAT_DATE_SECTIONS, ARCHIVED_CHAT_SECTION]
    .map((key) => [key, defaultChatSectionCollapsed(key)]));
}

type Snapshot = { session: number; groups: ChatList };

/**
 * The rows to show for `session`: a list, or an edit of the rows shown now (the drawer's own
 * while a dropped list is not read again). Queued in order, so edits in one tick all land.
 */
function nextSnapshot(prev: Snapshot, session: number, data: ChatList | ResourceUpdate<ChatList>): Snapshot {
  const groups = typeof data === "function" ? data(prev.session === session ? prev.groups : emptyChatList()) : data;
  return prev.session === session && prev.groups === groups ? prev : { session, groups };
}

/** The drawer's chats, kept per account: the hourly token rotation reads nothing (NET-11). */
export function useDrawerChatList({ isDrawerOpen }: Params) {
  const { account, getToken } = useAccountSession();
  const session = getSessionGeneration();
  const [snapshot, setSnapshot] = useState<Snapshot>(() => ({ session, groups: emptyChatList() }));
  const groups = useMemo(() => snapshot.session === session && account ? snapshot.groups : emptyChatList(), [snapshot, session, account]);
  const [loading, setLoading] = useState(false);
  const [collapsedSections, setCollapsedSections] = useState(initialCollapsedSections);
  const [error, setError] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const hasLoadedOnceRef = useRef(false);
  const mountedRef = useRef(true);
  const loadIdRef = useRef(0);
  const [, setTitlePendingTick] = useState(0);
  const reportFailure = useReadFailureReport();
  // Another account starts unloaded, and a load the last one started lands nowhere.
  useLayoutEffect(() => {
    hasLoadedOnceRef.current = false;
    loadIdRef.current++;
  }, [session]);
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

  const applyChatList = useCallback((data: ChatList | ResourceUpdate<ChatList>, fetched = true) => {
    if (!current()) return;
    setSnapshot((prev) => nextSnapshot(prev, session, data));
    if (fetched) hasLoadedOnceRef.current = true;
  }, [current, session]);
  const hydrateFromCache = useCallback(() => {
    if (!account || !current()) return false;
    // Under today's headings: a list from disk or from before midnight moves its chats.
    const cached = regroupCachedChatList();
    if (!cached) return false;
    const fetched = getChatListFetchedAt() != null;
    applyChatList(cached, fetched);
    return fetched;
  }, [account, current, applyChatList]);

  const load = useCallback(async (background = false, force = false) => {
    const token = getToken();
    if (!account || !token || !current()) return;
    if (!force && isChatListFresh() && hydrateFromCache()) return;
    const loadId = ++loadIdRef.current;
    if (!background) setLoading(true);
    setError(false);
    const result = await fetchChatList(token, { force, report: reportFailure });
    if (!current() || loadId !== loadIdRef.current) return;
    // A failed read hands back the list already shown (one restored from disk, say): not loaded yet.
    if (result.data) applyChatList(getCachedChatList() ?? result.data, !result.error);
    if (result.error && !background) setError(true);
    if (!background) setLoading(false);
  }, [account, getToken, current, hydrateFromCache, applyChatList, reportFailure]);

  const olderInFlightRef = useRef(false);
  /** The next page of older dated chats, when the list's end comes into view (CLAR-12). */
  const loadOlderChats = useCallback(async () => {
    const token = getToken();
    if (!account || !token || !current() || olderInFlightRef.current) return;
    olderInFlightRef.current = true;
    try {
      const grown = await fetchOlderChats(token);
      if (grown && current()) applyChatList(grown, false);
    } catch (caught) {
      // The rows shown stay; the next scroll to the end tries again.
      const error = caught instanceof Error ? caught : new Error(String(caught));
      if (current() && !isExpectedReadFailure(error)) reportFailure(error);
    } finally {
      olderInFlightRef.current = false;
    }
  }, [account, getToken, current, applyChatList, reportFailure]);

  const [archivedPaging, setArchivedPaging] = useState<"idle" | "loading" | "failed">("idle");
  /** The next page of archived chats, from the archived section's "Show more" row. */
  const loadMoreArchivedChats = useCallback(async () => {
    const token = getToken();
    if (!account || !token || !current()) return;
    setArchivedPaging("loading");
    try {
      const grown = await fetchMoreArchivedChats(token);
      if (grown && current()) applyChatList(grown, false);
      if (current()) setArchivedPaging("idle");
    } catch (caught) {
      const error = caught instanceof Error ? caught : new Error(String(caught));
      if (!current()) return;
      setArchivedPaging("failed");
      if (!isExpectedReadFailure(error)) reportFailure(error);
    }
  }, [account, getToken, current, applyChatList, reportFailure]);

  const handleRefresh = useCallback(async () => {
    if (!account || !current()) return;
    setRefreshing(true);
    try { await load(false, true); }
    finally { if (current()) setRefreshing(false); }
  }, [account, current, load]);

  // A cold start paints the chats this account had last time while the list is read again.
  useEffect(() => {
    const token = getToken();
    if (!account || !token) return;
    let cancelled = false;
    void restoreChatList(token).then((restored) => {
      if (restored && !cancelled && current()) hydrateFromCache();
    });
    return () => { cancelled = true; };
  }, [account, getToken, current, hydrateFromCache]);

  // Idle warm is only for first paint. Closing the drawer never triggers a read.
  useEffect(() => {
    hydrateFromCache();
    if (!shouldWarmClosedDrawerChatList({ hasToken: Boolean(account), isDrawerOpen, hasLoadedOnce: hasLoadedOnceRef.current })) return;
    const token = getToken();
    if (!token) return;
    let cancelled = false;
    const cancelIdle = scheduleIdleTask(() => {
      if (cancelled || !current()) return;
      void fetchChatList(token).then(({ data, error }) => {
        if (!cancelled && current() && data) applyChatList(getCachedChatList() ?? data, !error);
      });
    });
    return () => { cancelled = true; cancelIdle(); };
  }, [account, getToken, isDrawerOpen, current, hydrateFromCache, applyChatList]);

  useEffect(() => {
    hydrateFromCache();
    // A list dropped since (an unarchive in Settings) is read again: it was never fetched.
    if (drawerChatFetchMode({ isDrawerOpen, hasToken: Boolean(account), hasLoadedOnce: hasLoadedOnceRef.current && getChatListFetchedAt() != null }) !== "skip") void load();
  }, [isDrawerOpen, account, load, hydrateFromCache]);
  // The API back after an outage: the open drawer's chats, read as opening it reads them.
  const openRef = useLatestRef(isDrawerOpen);
  useReconnectRefresh(() => void load(), { onScreen: () => openRef.current, readAt: getChatListFetchedAt });

  const { patchChatInGroups, insertChatInGroups, removeChatFromGroupsById } = useListEdits({ account, current, applyChatList, load, openRef });
  const moveChatArchiveState = useCallback((chatId: string, archived: boolean) => {
    patchChatInGroups(chatId, archived ? { archived, pinned: false } : { archived });
  }, [patchChatInGroups]);

  useEffect(() => {
    const unregisters = [
      registerChatPatcher(patchChatInGroups),
      registerChatInserter(insertChatInGroups),
      registerChatRemover(removeChatFromGroupsById),
    ];
    return () => unregisters.forEach((unregister) => unregister());
  }, [patchChatInGroups, insertChatInGroups, removeChatFromGroupsById]);
  useEffect(() => subscribeChatTitleGenerating(() => setTitlePendingTick((n) => n + 1)), []);

  return {
    loading, error, refreshing, groups, allChats, load, handleRefresh,
    hasOlderChats: Boolean(groups.next_cursor), loadOlderChats,
    hasMoreArchived: Boolean(groups.archived_next_cursor), loadMoreArchivedChats, archivedPaging,
    patchChatInGroups, insertChatInGroups, isSectionCollapsed, toggleSectionCollapsed,
    moveChatArchiveState, removeChatFromGroupsById,
  };
}

type ListEditDeps = {
  account: string | null;
  current: () => boolean;
  applyChatList: (data: ChatList | ResourceUpdate<ChatList>, fetched?: boolean) => void;
  load: (background?: boolean) => Promise<void>;
  openRef: RefObject<boolean>;
};

/**
 * The drawer's own edits to its list (patch, insert, remove), cached and published. A list
 * Settings dropped takes no edit until it is read again (`updateChatListCache`): the edit lands
 * on the rows shown, which an unarchive left in place. A drop that removed rows (Delete all,
 * Archive all) clears them here first, so an edit can never bring one back. Either drop reads
 * the list again: at once with the drawer open, else in the background, so Home's last chat
 * and a new chat's title poll have it without the drawer.
 */
function useListEdits({ account, current, applyChatList, load, openRef }: ListEditDeps) {
  useEffect(() => subscribeChatList(() => {
    if (!current() || !isChatListDropped()) return;
    if (chatListRowsRemoved()) applyChatList(emptyChatList(), false);
    if (openRef.current) void load();
    else scheduleIdleTask(() => void load(true));
  }), [current, applyChatList, load, openRef]);
  const updateGroups = useCallback((chatId: string, patch: Partial<Chat> | null, update: (previous: ChatList) => ChatList) => {
    if (!account || !current()) return;
    applyChatList(updateChatListCache(update) ?? update, false);
    publishChatChange(chatId, patch);
  }, [account, current, applyChatList]);
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
  // A chat deleted elsewhere (Settings' archived chats) leaves only its own row.
  useEffect(() => onAppEvent("chatsDeleted", ({ chatIds }) => {
    chatIds.forEach((chatId) => removeChatFromGroupsById(chatId));
  }), [removeChatFromGroupsById]);
  return { patchChatInGroups, insertChatInGroups, removeChatFromGroupsById };
}

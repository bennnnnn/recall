import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { FlashList } from "@shopify/flash-list";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { closeDrawer, registerChatInserter, registerChatPatcher, startNewChatGlobal, isChatTitleGenerating, subscribeChatTitleGenerating } from "@/lib/drawer";
import { insertChatIntoGroups, emptyChatList } from "@/lib/drawerChatList";
import {
  activeChatsFromGroups,
  ARCHIVED_CHAT_SECTION,
  CHAT_DATE_SECTIONS,
  defaultChatSectionCollapsed,
  drawerSectionTitleKey,
  isCollapsibleChatSection,
  patchChatListGroups,
  PINNED_CHAT_SECTION,
  removeChatFromGroups,
  type ChatListSectionKey,
} from "@/lib/chatListSections";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Theme, useTheme } from "@/lib/theme";
import { ActionBanner } from "@/components/ActionBanner";
import { ChatActionsSheet } from "@/components/ChatActionsSheet";
import { ChatRenameSheet } from "@/components/ChatRenameSheet";
import { ReminderBadge } from "@/components/ReminderBadge";
import { useAuth } from "@/contexts/AuthContext";
import { useDrawer } from "@/contexts/DrawerContext";
import { useReminderBadgeCount } from "@/hooks/useReminderBadgeCount";
import { useDrawerSearch } from "@/hooks/useDrawerSearch";
import { api, Chat } from "@/lib/api";
import {
  bottomChromeFadeColors,
  BOTTOM_CHROME_FADE_LOCATIONS,
  topChromeFadeColors,
  TOP_CHROME_FADE_LOCATIONS,
} from "@/lib/chromeFade";
import { tap } from "@/lib/haptics";
import { scheduleIdleTask } from "@/lib/scheduleIdle";
import { DrawerSearchResults } from "@/components/drawer/DrawerSearchResults";
import {
  ConversationRow,
  makeConversationRowStyles,
} from "@/components/drawer/ConversationRow";
import { sanitizeManualChatTitle } from "@/lib/chatTitle";
import { shareConversation } from "@/lib/share";

const TOP_CHROME = 58;
const FOOTER_CHROME = 54;
const FADE_EXTRA = 40;
const CHAT_LIST_STALE_MS = 20_000;

export function ConversationList(_props: unknown) {
  const { token } = useAuth();
  const { isOpen } = useDrawer();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const rowStyles = useMemo(() => makeConversationRowStyles(theme), [theme]);
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const [loading, setLoading] = useState(true);
  const [groups, setGroups] = useState(emptyChatList);
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
  const {
    searchOpen,
    searchQuery,
    searchResults,
    searchLoading,
    searchError,
    hasSearchQuery,
    searchInputRef,
    openSearch,
    closeSearch,
    onSearchChange,
  } = useDrawerSearch({ token, isDrawerOpen: isOpen });
  const [, setTitlePendingTick] = useState(0);
  const [menuChat, setMenuChat] = useState<Chat | null>(null);
  const [renameVisible, setRenameVisible] = useState(false);
  const [renameText, setRenameText] = useState("");
  const [renameTarget, setRenameTarget] = useState<Chat | null>(null);
  const [actionBanner, setActionBanner] = useState<{
    message: string;
    icon?: keyof typeof Ionicons.glyphMap;
  } | null>(null);
  const { unseenCount, showIndicator } = useReminderBadgeCount({
    enabled: Boolean(token),
  });

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

  const matchingChatIds = useMemo(
    () => new Set(searchResults.map((result) => result.chat_id)),
    [searchResults],
  );

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
    if (!isOpen) return;
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
  }, [isOpen, load, allChats.length]);

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

  useEffect(() => {
    if (!isOpen) setMenuChat(null);
  }, [isOpen]);

  const showActionBanner = useCallback(
    (message: string, icon?: keyof typeof Ionicons.glyphMap) => {
      setActionBanner({ message, icon });
    },
    [],
  );

  const dismissActionBanner = useCallback(() => setActionBanner(null), []);

  const closeMenu = useCallback(() => setMenuChat(null), []);

  const handleShareChat = useCallback(async () => {
    if (!token || !menuChat) return;
    const chat = menuChat;
    closeMenu();
    try {
      const msgs = await api.listAllMessages(token, chat.id);
      await shareConversation(chat.title, msgs);
    } catch {
      Alert.alert(t("common.error"), t("chat.share_failed"));
    }
  }, [token, menuChat, closeMenu, t]);

  const openRenameFromMenu = useCallback(() => {
    if (!menuChat) return;
    setRenameTarget(menuChat);
    setRenameText(menuChat.title ?? "");
    closeMenu();
    setRenameVisible(true);
  }, [menuChat, closeMenu]);

  const confirmRename = useCallback(async () => {
    const title = sanitizeManualChatTitle(renameText);
    if (!title || !renameTarget || !token) {
      setRenameVisible(false);
      return;
    }
    const prevTitle = renameTarget.title;
    patchChatInGroups(renameTarget.id, { title });
    setRenameVisible(false);
    setRenameTarget(null);
    try {
      await api.renameChat(token, renameTarget.id, title);
      showActionBanner(t("chat.renamed_toast"), "pencil-outline");
    } catch {
      patchChatInGroups(renameTarget.id, { title: prevTitle ?? null });
      Alert.alert(t("common.error"), t("chat.rename_failed"));
    }
  }, [renameText, renameTarget, token, patchChatInGroups, showActionBanner, t]);

  const togglePinChat = useCallback(async () => {
    if (!token || !menuChat) return;
    const chat = menuChat;
    const next = !chat.pinned;
    closeMenu();
    moveChatPinState(chat.id, next);
    try {
      await api.setPin(token, chat.id, next);
      showActionBanner(
        next ? t("chat.pinned_toast") : t("chat.unpinned_toast"),
        next ? "bookmark" : "bookmark-outline",
      );
    } catch {
      moveChatPinState(chat.id, !next);
      Alert.alert(t("common.error"), t("chat.pin_failed"));
    }
  }, [token, menuChat, closeMenu, moveChatPinState, showActionBanner, t]);

  const toggleArchiveChat = useCallback(async () => {
    if (!token || !menuChat) return;
    const chat = menuChat;
    const next = !chat.archived;
    closeMenu();
    try {
      await api.setArchive(token, chat.id, next);
      await load(true);
      showActionBanner(
        next ? t("chat.archived_toast") : t("chat.unarchived_toast"),
        next ? "archive-outline" : "arrow-undo-outline",
      );
    } catch {
      Alert.alert(t("common.error"), t("common.error"));
    }
  }, [token, menuChat, closeMenu, load, showActionBanner, t]);

  const confirmDeleteChat = useCallback(() => {
    if (!menuChat) return;
    const chat = menuChat;
    closeMenu();
    Alert.alert(t("chat.delete_confirm_title"), t("chat.delete_confirm_body"), [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("common.delete"),
        style: "destructive",
        onPress: async () => {
          if (!token) return;
          try {
            await api.deleteChat(token, chat.id);
            await load(true);
            showActionBanner(t("chat.deleted_toast"), "trash-outline");
          } catch {
            Alert.alert(t("common.error"), t("chat.delete_failed"));
          }
        },
      },
    ]);
  }, [menuChat, closeMenu, token, load, showActionBanner, t]);

  const openChat = (id: string, messageId?: string | null) => {
    closeDrawer();
    closeSearch();
    router.setParams({
      chatId: id,
      ...(messageId ? { highlightMessage: messageId } : { highlightMessage: undefined }),
    });
  };

  const newChat = () => {
    closeDrawer();
    startNewChatGlobal();
  };

  const openLists = () => {
    closeDrawer();
    router.push({ pathname: "/todos", params: { focus: "list" } });
  };

  const openReminders = () => {
    closeDrawer();
    router.push({ pathname: "/todos", params: { focus: "reminders" } });
  };

  const openProjects = () => {
    closeDrawer();
    router.push("/projects");
  };

  const showRowMenu = (chat: Chat) => {
    tap();
    setMenuChat(chat);
  };

  const topInset = insets.top + 8 + TOP_CHROME;
  const bottomInset = insets.bottom + 8 + FOOTER_CHROME;
  const topFadeHeight = topInset + FADE_EXTRA;
  const bottomFadeHeight = bottomInset + FADE_EXTRA;

  const drawerNav = (
    <View style={s.drawerNav}>
      <Pressable style={s.todosLink} onPress={openProjects}>
        <Ionicons name="folder-outline" size={18} color={theme.primary} />
        <Text style={s.todosLinkText}>{t("drawer.projects")}</Text>
        <Ionicons
          name="chevron-forward"
          size={16}
          color={theme.textTertiary}
          style={s.todosChevron}
        />
      </Pressable>

      <Pressable style={s.todosLink} onPress={openLists}>
        <Ionicons name="list-outline" size={18} color={theme.primary} />
        <Text style={s.todosLinkText}>{t("drawer.lists")}</Text>
        <Ionicons
          name="chevron-forward"
          size={16}
          color={theme.textTertiary}
          style={s.todosChevron}
        />
      </Pressable>

      <Pressable style={s.todosLink} onPress={openReminders}>
        <View style={s.navIconWrap}>
          <Ionicons
            name={showIndicator ? "notifications" : "notifications-outline"}
            size={18}
            color={theme.primary}
          />
          {showIndicator ? (
            <ReminderBadge count={unseenCount} style={s.navBadge} />
          ) : null}
        </View>
        <Text style={s.todosLinkText}>{t("drawer.reminders")}</Text>
        <Ionicons
          name="chevron-forward"
          size={16}
          color={theme.textTertiary}
          style={s.todosChevron}
        />
      </Pressable>
    </View>
  );

  // Flatten the sectioned chat list into header + row items so FlashList can
  // virtualize rows (the long part) instead of mounting every chat in a
  // ScrollView. Section styling is just a top margin + padded title (no card
  // background), so header items reproduce the look exactly.
  type ChatListItem =
    | {
        type: "sectionHeader";
        key: ChatListSectionKey;
        title: string;
        count: number;
        collapsible: boolean;
      }
    | { type: "row"; key: string; chat: Chat };

  const highlightedIds = searchOpen ? matchingChatIds : undefined;

  const chatListData = useMemo<ChatListItem[]>(() => {
    if (allChats.length === 0 && groups.archived.length === 0) return [];
    const items: ChatListItem[] = [];
    const sections: { key: ChatListSectionKey; chats: Chat[] }[] = [
      { key: PINNED_CHAT_SECTION, chats: groups.pinned },
      ...CHAT_DATE_SECTIONS.map((key) => ({ key, chats: groups[key] })),
      { key: ARCHIVED_CHAT_SECTION, chats: groups.archived },
    ];

    for (const section of sections) {
      if (section.chats.length === 0) continue;
      items.push({
        type: "sectionHeader",
        key: section.key,
        title: t(drawerSectionTitleKey(section.key)),
        count: section.chats.length,
        collapsible: isCollapsibleChatSection(section.key),
      });
      if (isSectionCollapsed(section.key)) continue;
      for (const chat of section.chats) {
        items.push({ type: "row", key: chat.id, chat });
      }
    }
    return items;
  }, [allChats.length, groups, isSectionCollapsed, t]);

  const renderChatItem = useCallback(
    ({ item }: { item: ChatListItem }) => {
      if (item.type === "sectionHeader") {
        if (!item.collapsible) {
          return (
            <Text style={[s.sectionTitle, s.section]}>{item.title}</Text>
          );
        }
        const collapsed = isSectionCollapsed(item.key);
        return (
          <Pressable
            style={[s.sectionHeader, s.section]}
            onPress={() => toggleSectionCollapsed(item.key)}
            accessibilityRole="button"
            accessibilityState={{ expanded: !collapsed }}
          >
            <Text style={s.sectionTitle}>{item.title}</Text>
            <Text style={s.sectionCount}>{item.count}</Text>
            <Ionicons
              name={collapsed ? "chevron-down" : "chevron-up"}
              size={16}
              color={theme.textTertiary}
            />
          </Pressable>
        );
      }
      return (
        <ConversationRow
          chat={item.chat}
          rowStyles={rowStyles}
          highlighted={highlightedIds?.has(item.chat.id) ?? false}
          titleGenerating={isChatTitleGenerating(item.chat.id)}
          onOpen={() => openChat(item.chat.id)}
          onLongPress={() => showRowMenu(item.chat)}
        />
      );
    },
    [
      s,
      rowStyles,
      highlightedIds,
      isSectionCollapsed,
      toggleSectionCollapsed,
      theme,
      openChat,
      showRowMenu,
    ],
  );

  const chatListEmpty =
    allChats.length === 0 && !loading && !error ? (
      <View style={s.inlineEmpty}>
        <Text style={s.emptyText}>{t("drawer.no_conversations")}</Text>
      </View>
    ) : null;

  const searchSection = searchOpen ? (
    <DrawerSearchResults
      hasSearchQuery={hasSearchQuery}
      searchLoading={searchLoading}
      searchError={searchError}
      searchResults={searchResults}
      onOpenChat={openChat}
    />
  ) : null;

  const listHeader = (
    <>
      {drawerNav}
      {loading && allChats.length === 0 && !searchOpen ? (
        <View style={s.inlineEmpty}>
          <ActivityIndicator color={theme.primary} />
        </View>
      ) : error && allChats.length === 0 ? (
        <View style={s.inlineEmpty}>
          <Ionicons
            name="cloud-offline-outline"
            size={36}
            color={theme.textTertiary}
          />
          <Text style={s.emptyText}>{t("drawer.cant_reach")}</Text>
          <Pressable style={s.retryBtn} onPress={() => void load()}>
            <Text style={s.retryText}>{t("common.retry")}</Text>
          </Pressable>
        </View>
      ) : null}
      {searchSection}
    </>
  );

  const listBody = (
    <FlashList
      style={s.list}
      data={chatListData}
      renderItem={renderChatItem}
      keyExtractor={(item) => item.key}
      getItemType={(item) => item.type}
      showsVerticalScrollIndicator={false}
      contentContainerStyle={{
        paddingTop: topInset,
        paddingBottom: bottomInset,
      }}
      keyboardShouldPersistTaps="handled"
      ListHeaderComponent={listHeader}
      ListEmptyComponent={chatListEmpty}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={handleRefresh}
          colors={[theme.primary]}
          tintColor={theme.primary}
        />
      }
    />
  );

  const topFadeColors = topChromeFadeColors(theme);
  const bottomFadeColors = bottomChromeFadeColors(theme);

  return (
    <View style={s.root}>
      <ActionBanner
        message={actionBanner?.message ?? null}
        icon={actionBanner?.icon}
        bottomOffset={FOOTER_CHROME + 16}
        onDismiss={dismissActionBanner}
      />
      <ChatActionsSheet
        visible={menuChat != null}
        title={menuChat?.title ?? null}
        pinned={menuChat?.pinned ?? false}
        archived={menuChat?.archived ?? false}
        onClose={closeMenu}
        onShare={() => {
          tap();
          void handleShareChat();
        }}
        onRename={() => {
          tap();
          openRenameFromMenu();
        }}
        onTogglePin={() => {
          tap();
          void togglePinChat();
        }}
        onToggleArchive={() => {
          tap();
          void toggleArchiveChat();
        }}
        onDelete={() => {
          tap();
          confirmDeleteChat();
        }}
      />
      <ChatRenameSheet
        visible={renameVisible}
        value={renameText}
        onChangeText={setRenameText}
        onClose={() => {
          setRenameVisible(false);
          setRenameTarget(null);
        }}
        onSave={() => void confirmRename()}
      />
      {listBody}

      <LinearGradient
        colors={topFadeColors as [string, string, ...string[]]}
        locations={[...TOP_CHROME_FADE_LOCATIONS]}
        style={[s.topFade, { height: topFadeHeight }]}
        pointerEvents="none"
      />

      <LinearGradient
        colors={bottomFadeColors as [string, string, ...string[]]}
        locations={[...BOTTOM_CHROME_FADE_LOCATIONS]}
        style={[s.bottomFade, { height: bottomFadeHeight }]}
        pointerEvents="none"
      />

      <View
        style={[s.topOverlay, { paddingTop: insets.top + 8 }]}
        pointerEvents="box-none"
      >
        <View style={s.header}>
          {searchOpen ? (
            <View style={s.searchBar}>
              <Ionicons name="search-outline" size={18} color={theme.textSecondary} />
              <TextInput
                ref={searchInputRef}
                style={s.searchInput}
                placeholder={t("search.placeholder")}
                placeholderTextColor={theme.textTertiary}
                value={searchQuery}
                onChangeText={onSearchChange}
                returnKeyType="search"
                autoCorrect={false}
                clearButtonMode="while-editing"
              />
              <Pressable hitSlop={8} onPress={closeSearch} style={s.searchCancel}>
                <Text style={s.searchCancelText}>{t("common.cancel")}</Text>
              </Pressable>
            </View>
          ) : (
            <View style={s.logo}>
              <View style={s.logoIcon}>
                <Text style={s.logoStar}>✦</Text>
              </View>
              <Text style={s.logoText}>Recall</Text>
              <Pressable hitSlop={8} style={s.searchBtn} onPress={openSearch}>
                <Ionicons
                  name="search-outline"
                  size={20}
                  color={theme.textSecondary}
                />
              </Pressable>
            </View>
          )}
        </View>
      </View>

      <View
        style={[s.footer, { paddingBottom: insets.bottom + 8 }]}
        pointerEvents="box-none"
      >
        <Pressable style={s.footerNewChat} onPress={newChat}>
          <Ionicons name="create-outline" size={18} color={theme.onPrimary} />
          <Text style={s.footerNewChatText}>{t("drawer.new_chat")}</Text>
        </Pressable>
        <Pressable
          style={s.settingsBtn}
          onPress={() => {
            closeDrawer();
            router.push("/settings");
          }}
        >
          <Ionicons name="settings-outline" size={22} color={theme.onPrimary} />
        </Pressable>
      </View>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.bg, overflow: "visible" },
  center: { flex: 1, alignItems: "center", justifyContent: "center", gap: 8 },
  topFade: { position: "absolute", top: 0, left: 0, right: 0, zIndex: 50 },
  bottomFade: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    zIndex: 50,
  },
  topOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    zIndex: 100,
    backgroundColor: "transparent",
  },
  header: { paddingHorizontal: 16, paddingBottom: 10 },
  drawerNav: {
    paddingBottom: 14,
    marginBottom: 4,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: theme.border,
  },
  logo: { flexDirection: "row", alignItems: "center", gap: 8 },
  logoIcon: {
    width: 28,
    height: 28,
    borderRadius: 8,
    backgroundColor: theme.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  logoStar: { fontSize: 13, color: theme.onPrimary },
  logoText: {
    fontSize: 20,
    fontWeight: "800",
    color: theme.text,
    letterSpacing: -0.5,
  },
  searchBtn: { marginLeft: 2, padding: 4 },
  searchBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: theme.surface,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  searchInput: {
    flex: 1,
    fontSize: 16,
    color: theme.text,
    paddingVertical: 0,
    minHeight: 22,
  },
  searchCancel: { paddingLeft: 4 },
  searchCancelText: { fontSize: 15, fontWeight: "600", color: theme.primary },
  searchResult: {
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: theme.border,
    gap: 4,
  },
  searchResultHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  searchResultTitle: { flex: 1, fontSize: 13, color: theme.textSecondary },
  searchResultBadge: {
    fontSize: 10,
    fontWeight: "700",
    color: theme.primary,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  searchResultSnippet: { fontSize: 15, lineHeight: 21, color: theme.text },
  searchHint: {
    fontSize: 14,
    color: theme.textSecondary,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  searchStatus: {
    paddingVertical: 12,
    alignItems: "center",
  },
  todosLink: {
    flexDirection: "row",
    alignItems: "center",
    marginHorizontal: 14,
    marginBottom: 4,
    paddingHorizontal: 14,
    paddingVertical: 10,
    gap: 10,
  },
  todosLinkText: { flex: 1, fontSize: 15, fontWeight: "600", color: theme.text },
  todosChevron: { marginLeft: "auto" },
  navIconWrap: {
    width: 22,
    height: 22,
    alignItems: "center",
    justifyContent: "center",
  },
  navBadge: { position: "absolute", top: -6, right: -10 },
  inlineEmpty: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 32,
    gap: 8,
  },
  list: { flex: 1 },
  section: { marginTop: 18 },
  sectionTitle: {
    fontSize: 11,
    fontWeight: "700",
    color: theme.textTertiary,
    textTransform: "uppercase",
    letterSpacing: 0.8,
    paddingHorizontal: 14,
    marginBottom: 2,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: 18,
    paddingHorizontal: 14,
    paddingVertical: 4,
  },
  sectionCount: {
    fontSize: 12,
    color: theme.textTertiary,
    marginLeft: "auto",
  },
  emptyText: { fontSize: 15, color: theme.textSecondary, fontWeight: "500" },
  retryBtn: {
    paddingHorizontal: 20,
    paddingVertical: 8,
    borderRadius: 10,
    backgroundColor: theme.primary,
  },
  retryText: { fontSize: 14, fontWeight: "600", color: theme.onPrimary },
  footer: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    zIndex: 100,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 14,
    paddingTop: 12,
    backgroundColor: "transparent",
  },
  footerNewChat: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 8,
    paddingHorizontal: 10,
    borderRadius: 10,
    backgroundColor: theme.primary,
  },
  footerNewChatText: { fontSize: 14, fontWeight: "600", color: theme.onPrimary },
  settingsBtn: {
    marginLeft: "auto",
    padding: 8,
    borderRadius: 10,
    backgroundColor: theme.primary,
  },
  });
}

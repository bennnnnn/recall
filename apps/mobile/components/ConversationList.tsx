import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { closeDrawer, startNewChatGlobal } from "@/lib/drawer";
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
import { api, Chat, SearchResult } from "@/lib/api";
import { tap } from "@/lib/haptics";
import { scheduleIdleTask } from "@/lib/scheduleIdle";
import { shareConversation } from "@/lib/share";

const TOP_CHROME = 58;
const FOOTER_CHROME = 54;
const FADE_EXTRA = 40;
const CHAT_LIST_STALE_MS = 20_000;

function ChatRow({
  chat,
  onOpen,
  onLongPress,
  highlighted = false,
  rowStyles: r,
}: {
  chat: Chat;
  onOpen: () => void;
  onLongPress: () => void;
  highlighted?: boolean;
  rowStyles: ReturnType<typeof makeRowStyles>;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <Pressable
      style={[r.row, highlighted && r.rowHighlighted]}
      onPress={onOpen}
      onLongPress={onLongPress}
    >
      <Ionicons
        name={chat.pinned ? "bookmark" : "chatbubble-outline"}
        size={16}
        color={chat.pinned ? theme.primary : theme.textTertiary}
        style={r.rowIcon}
      />
      <Text style={r.title} numberOfLines={1}>
        {chat.title ?? t("common.untitled")}
      </Text>
    </Pressable>
  );
}

function Section({
  title,
  chats,
  onOpen,
  onLongPress,
  highlightedIds,
  rowStyles,
  sectionStyles,
}: {
  title: string;
  chats: Chat[];
  onOpen: (id: string) => void;
  onLongPress: (chat: Chat) => void;
  highlightedIds?: Set<string>;
  rowStyles: ReturnType<typeof makeRowStyles>;
  sectionStyles: ReturnType<typeof makeStyles>;
}) {
  if (!chats.length) return null;
  return (
    <View style={sectionStyles.section}>
      {title ? <Text style={sectionStyles.sectionTitle}>{title}</Text> : null}
      {chats.map((c) => (
        <ChatRow
          key={c.id}
          chat={c}
          rowStyles={rowStyles}
          highlighted={highlightedIds?.has(c.id) ?? false}
          onOpen={() => onOpen(c.id)}
          onLongPress={() => onLongPress(c)}
        />
      ))}
    </View>
  );
}

export function ConversationList(_props: unknown) {
  const { token } = useAuth();
  const { isOpen } = useDrawer();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const rowStyles = useMemo(() => makeRowStyles(theme), [theme]);
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const [loading, setLoading] = useState(true);
  const [groups, setGroups] = useState<{
    pinned: Chat[];
    today: Chat[];
    yesterday: Chat[];
    earlier: Chat[];
    archived: Chat[];
  }>({ pinned: [], today: [], yesterday: [], earlier: [], archived: [] });
  const [archivedExpanded, setArchivedExpanded] = useState(false);
  const [error, setError] = useState(false);
  const lastFetchedRef = useRef(0);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState(false);
  const searchInputRef = useRef<TextInput>(null);
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
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

  const allChats = useMemo(
    () => [
      ...groups.pinned,
      ...groups.today,
      ...groups.yesterday,
      ...groups.earlier,
    ],
    [groups],
  );

  const matchingChatIds = useMemo(
    () => new Set(searchResults.map((result) => result.chat_id)),
    [searchResults],
  );

  const hasSearchQuery = searchQuery.trim().length > 0;

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
          earlier: chatGroups.earlier,
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
    setGroups((prev) => {
      const apply = (list: Chat[]) =>
        list.map((c) => (c.id === chatId ? { ...c, ...patch } : c));
      return {
        pinned: apply(prev.pinned),
        today: apply(prev.today),
        yesterday: apply(prev.yesterday),
        earlier: apply(prev.earlier),
        archived: apply(prev.archived),
      };
    });
  }, []);

  const moveChatPinState = useCallback((chatId: string, pinned: boolean) => {
    setGroups((prev) => {
      const all = [...prev.pinned, ...prev.today, ...prev.yesterday, ...prev.earlier];
      const chat = all.find((c) => c.id === chatId);
      if (!chat) return prev;
      const updated = { ...chat, pinned };
      const rest = {
        pinned: prev.pinned.filter((c) => c.id !== chatId),
        today: prev.today.filter((c) => c.id !== chatId),
        yesterday: prev.yesterday.filter((c) => c.id !== chatId),
        earlier: prev.earlier.filter((c) => c.id !== chatId),
        archived: prev.archived.filter((c) => c.id !== chatId),
      };
      if (pinned) {
        return { ...rest, pinned: [updated, ...rest.pinned] };
      }
      return { ...rest, today: [updated, ...rest.today] };
    });
  }, []);

  const closeSearch = useCallback(() => {
    setSearchOpen(false);
    setSearchQuery("");
    setSearchResults([]);
    setSearchError(false);
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
  }, []);

  const openSearch = useCallback(() => {
    setSearchOpen(true);
    requestAnimationFrame(() => searchInputRef.current?.focus());
  }, []);

  const doSearch = useCallback(
    async (q: string) => {
      if (!token || !q.trim()) {
        setSearchResults([]);
        setSearchError(false);
        return;
      }
      setSearchLoading(true);
      setSearchError(false);
      try {
        const data = await api.search(token, q.trim());
        setSearchResults(data.results);
      } catch {
        setSearchError(true);
        setSearchResults([]);
      } finally {
        setSearchLoading(false);
      }
    },
    [token],
  );

  const onSearchChange = (text: string) => {
    setSearchQuery(text);
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    searchTimerRef.current = setTimeout(() => {
      void doSearch(text);
    }, 300);
  };

  useEffect(() => {
    if (!isOpen) closeSearch();
  }, [isOpen, closeSearch]);

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
    const title = renameText.trim();
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

  useEffect(() => {
    return () => {
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    };
  }, []);

  const openChat = (id: string) => {
    closeDrawer();
    router.setParams({ chatId: id });
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

  const chatSections =
    allChats.length === 0 ? (
      <View style={s.inlineEmpty}>
        <Text style={s.emptyText}>{t("drawer.no_conversations")}</Text>
      </View>
    ) : (
      <>
        <Section
          title={t("drawer.pinned")}
          chats={groups.pinned}
          rowStyles={rowStyles}
          sectionStyles={s}
          highlightedIds={searchOpen ? matchingChatIds : undefined}
          onOpen={openChat}
          onLongPress={showRowMenu}
        />
        <Section
          title={t("drawer.today")}
          chats={groups.today}
          rowStyles={rowStyles}
          sectionStyles={s}
          highlightedIds={searchOpen ? matchingChatIds : undefined}
          onOpen={openChat}
          onLongPress={showRowMenu}
        />
        <Section
          title={t("drawer.yesterday")}
          chats={groups.yesterday}
          rowStyles={rowStyles}
          sectionStyles={s}
          highlightedIds={searchOpen ? matchingChatIds : undefined}
          onOpen={openChat}
          onLongPress={showRowMenu}
        />
        <Section
          title={t("drawer.earlier")}
          chats={groups.earlier}
          rowStyles={rowStyles}
          sectionStyles={s}
          onOpen={openChat}
          onLongPress={showRowMenu}
        />
        {groups.archived.length > 0 ? (
          <>
            <Pressable
              style={s.archivedHeader}
              onPress={() => setArchivedExpanded((v) => !v)}
            >
              <Text style={s.sectionTitle}>{t("drawer.archived")}</Text>
              <Text style={s.archivedCount}>{groups.archived.length}</Text>
              <Ionicons
                name={archivedExpanded ? "chevron-up" : "chevron-down"}
                size={16}
                color={theme.textTertiary}
              />
            </Pressable>
            {archivedExpanded ? (
              <Section
                title=""
                chats={groups.archived}
                rowStyles={rowStyles}
                sectionStyles={s}
                onOpen={openChat}
                onLongPress={showRowMenu}
              />
            ) : null}
          </>
        ) : null}
      </>
    );

  const searchSection = searchOpen ? (
    <View style={s.section}>
      <Text style={s.sectionTitle}>{t("search.results")}</Text>
      {!hasSearchQuery ? (
        <Text style={s.searchHint}>{t("search.empty")}</Text>
      ) : searchLoading ? (
        <View style={s.searchStatus}>
          <ActivityIndicator size="small" color={theme.primary} />
        </View>
      ) : searchError ? (
        <Text style={s.searchHint}>{t("common.error")}</Text>
      ) : searchResults.length === 0 ? (
        <Text style={s.searchHint}>{t("search.no_results")}</Text>
      ) : (
        searchResults.map((result) => (
          <Pressable
            key={
              result.message_id
                ? result.message_id
                : `title-${result.chat_id}`
            }
            style={s.searchResult}
            onPress={() => openChat(result.chat_id)}
          >
            <View style={s.searchResultHeader}>
              <Ionicons
                name={
                  result.match_type === "title"
                    ? "chatbubble-outline"
                    : result.role === "user"
                      ? "person-outline"
                      : "sparkles-outline"
                }
                size={14}
                color={result.match_type === "title" ? theme.primary : theme.textSecondary}
              />
              <Text style={s.searchResultTitle} numberOfLines={1}>
                {result.chat_title ?? t("common.untitled")}
              </Text>
              {result.match_type === "title" ? (
                <Text style={s.searchResultBadge}>{t("search.topic_match")}</Text>
              ) : null}
            </View>
            <Text style={s.searchResultSnippet} numberOfLines={2}>
              {result.content}
            </Text>
          </Pressable>
        ))
      )}
    </View>
  ) : null;

  const listBody = (
    <ScrollView
      style={s.list}
      showsVerticalScrollIndicator={false}
      contentContainerStyle={{
        paddingTop: topInset,
        paddingBottom: bottomInset,
      }}
      keyboardShouldPersistTaps="handled"
    >
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
      ) : (
        <>
          {searchSection}
          {chatSections}
        </>
      )}
    </ScrollView>
  );

  const topFadeColors = theme.isDark
    ? [theme.bg, `${theme.bg}FA`, `${theme.bg}D0`, `${theme.bg}70`, `${theme.bg}00`]
    : [
        theme.bg,
        "rgba(255,255,255,0.98)",
        "rgba(255,255,255,0.82)",
        "rgba(255,255,255,0.45)",
        "rgba(255,255,255,0)",
      ];
  const bottomFadeColors = theme.isDark
    ? [`${theme.bg}00`, `${theme.bg}70`, `${theme.bg}D0`, theme.bg]
    : [
        "rgba(255,255,255,0)",
        "rgba(255,255,255,0.45)",
        "rgba(255,255,255,0.82)",
        "rgba(255,255,255,0.95)",
      ];

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
        locations={[0, 0.25, 0.5, 0.78, 1]}
        style={[s.topFade, { height: topFadeHeight }]}
        pointerEvents="none"
      />

      <LinearGradient
        colors={bottomFadeColors as [string, string, ...string[]]}
        locations={theme.isDark ? [0, 0.35, 0.72, 1] : [0, 0.35, 0.72, 1]}
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
          <Ionicons name="create-outline" size={18} color="#fff" />
          <Text style={s.footerNewChatText}>{t("drawer.new_chat")}</Text>
        </Pressable>
        <Pressable
          style={s.settingsBtn}
          onPress={() => {
            closeDrawer();
            router.push("/settings");
          }}
        >
          <Ionicons name="settings-outline" size={22} color="#fff" />
        </Pressable>
      </View>
    </View>
  );
}

function makeRowStyles(theme: Theme) {
  return StyleSheet.create({
    row: {
      flexDirection: "row",
      alignItems: "center",
      paddingVertical: 9,
      paddingHorizontal: 14,
      gap: 10,
    },
    rowIcon: { flexShrink: 0 },
    title: { flex: 1, fontSize: 14, fontWeight: "500", color: theme.text },
    rowHighlighted: {
      backgroundColor: theme.primaryLight,
      borderRadius: 10,
      marginHorizontal: 6,
      paddingHorizontal: 8,
    },
  });
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
  logoStar: { fontSize: 13, color: "#fff" },
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
  archivedHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: 18,
    paddingHorizontal: 14,
    paddingVertical: 4,
  },
  archivedCount: {
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
  retryText: { fontSize: 14, fontWeight: "600", color: "#fff" },
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
  footerNewChatText: { fontSize: 14, fontWeight: "600", color: "#fff" },
  settingsBtn: {
    marginLeft: "auto",
    padding: 8,
    borderRadius: 10,
    backgroundColor: theme.primary,
  },
  });
}

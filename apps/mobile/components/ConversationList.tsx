import { useCallback, useMemo } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  Text,
  View,
} from "react-native";
import { FlashList } from "@shopify/flash-list";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { closeDrawer, startNewChatGlobal, isChatTitleGenerating } from "@/lib/drawer";
import {
  ARCHIVED_CHAT_SECTION,
  CHAT_DATE_SECTIONS,
  drawerSectionTitleKey,
  isCollapsibleChatSection,
  PINNED_CHAT_SECTION,
  type ChatListSectionKey,
} from "@/lib/chatListSections";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { useTheme } from "@/lib/theme";
import { ActionBanner } from "@/components/ActionBanner";
import { ChatActionsSheet } from "@/components/ChatActionsSheet";
import { ChatRenameSheet } from "@/components/ChatRenameSheet";
import { useAuth } from "@/contexts/AuthContext";
import { useDrawer } from "@/contexts/DrawerContext";
import { useDrawerChatActions } from "@/hooks/useDrawerChatActions";
import { useDrawerChatList } from "@/hooks/useDrawerChatList";
import { useReminderBadgeCount } from "@/hooks/useReminderBadgeCount";
import { useDrawerSearch } from "@/hooks/useDrawerSearch";
import { Chat } from "@/lib/api";
import {
  bottomChromeFadeColors,
  BOTTOM_CHROME_FADE_LOCATIONS,
  topChromeFadeColors,
  TOP_CHROME_FADE_LOCATIONS,
} from "@/lib/chromeFade";
import { tap } from "@/lib/haptics";
import { DrawerSearchResults } from "@/components/drawer/DrawerSearchResults";
import { DrawerFooter } from "@/components/drawer/DrawerFooter";
import { DrawerHeader } from "@/components/drawer/DrawerHeader";
import { DrawerNavLinks } from "@/components/drawer/DrawerNavLinks";
import {
  FADE_EXTRA,
  FOOTER_CHROME,
  makeConversationListStyles,
  TOP_CHROME,
} from "@/components/drawer/conversationListStyles";
import {
  ConversationRow,
  makeConversationRowStyles,
} from "@/components/drawer/ConversationRow";

export function ConversationList(_props: unknown) {
  const { token } = useAuth();
  const { isOpen } = useDrawer();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeConversationListStyles(theme), [theme]);
  const rowStyles = useMemo(() => makeConversationRowStyles(theme), [theme]);
  const router = useRouter();
  const insets = useSafeAreaInsets();

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

  const {
    loading,
    error,
    refreshing,
    groups,
    allChats,
    load,
    handleRefresh,
    patchChatInGroups,
    isSectionCollapsed,
    toggleSectionCollapsed,
    moveChatPinState,
  } = useDrawerChatList({ token, isDrawerOpen: isOpen });

  const {
    menuChat,
    renameVisible,
    renameText,
    setRenameText,
    actionBanner,
    dismissActionBanner,
    closeMenu,
    showRowMenu,
    handleShareChat,
    openRenameFromMenu,
    confirmRename,
    togglePinChat,
    toggleArchiveChat,
    confirmDeleteChat,
    closeRename,
  } = useDrawerChatActions({
    token,
    isDrawerOpen: isOpen,
    patchChatInGroups,
    load,
    moveChatPinState,
  });

  const { unseenCount, showIndicator } = useReminderBadgeCount({
    enabled: Boolean(token),
  });

  const matchingChatIds = useMemo(
    () => new Set(searchResults.map((result) => result.chat_id)),
    [searchResults],
  );

  const openChat = useCallback(
    (id: string, messageId?: string | null) => {
      closeDrawer();
      closeSearch();
      router.setParams({
        chatId: id,
        ...(messageId ? { highlightMessage: messageId } : { highlightMessage: undefined }),
      });
    },
    [closeSearch, router],
  );

  const newChat = useCallback(() => {
    closeDrawer();
    startNewChatGlobal();
  }, []);

  const openLists = useCallback(() => {
    closeDrawer();
    router.push({ pathname: "/todos", params: { focus: "list" } });
  }, [router]);

  const openReminders = useCallback(() => {
    closeDrawer();
    router.push({ pathname: "/todos", params: { focus: "reminders" } });
  }, [router]);

  const openProjects = useCallback(() => {
    closeDrawer();
    router.push("/projects");
  }, [router]);

  const onShowRowMenu = useCallback(
    (chat: Chat) => {
      tap();
      showRowMenu(chat);
    },
    [showRowMenu],
  );

  const topInset = insets.top + 8 + TOP_CHROME;
  const bottomInset = insets.bottom + 8 + FOOTER_CHROME;
  const topFadeHeight = topInset + FADE_EXTRA;
  const bottomFadeHeight = bottomInset + FADE_EXTRA;

  const drawerNav = (
    <DrawerNavLinks
      styles={s}
      theme={theme}
      showIndicator={showIndicator}
      unseenCount={unseenCount}
      onProjects={openProjects}
      onLists={openLists}
      onReminders={openReminders}
    />
  );

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
          onLongPress={() => onShowRowMenu(item.chat)}
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
      onShowRowMenu,
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
        onClose={closeRename}
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

      <DrawerHeader
        styles={s}
        theme={theme}
        paddingTop={insets.top + 8}
        searchOpen={searchOpen}
        searchQuery={searchQuery}
        searchInputRef={searchInputRef}
        onSearchChange={onSearchChange}
        onOpenSearch={openSearch}
        onCloseSearch={closeSearch}
      />

      <DrawerFooter
        styles={s}
        theme={theme}
        paddingBottom={insets.bottom + 8}
        onNewChat={newChat}
        onSettings={() => {
          closeDrawer();
          router.push("/settings");
        }}
      />
    </View>
  );
}

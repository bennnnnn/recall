import { useCallback, useMemo } from "react";
import {
  ActivityIndicator,
  Pressable,
  Text,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { closeDrawer, startNewChatGlobal } from "@/lib/drawer";
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
import { DrawerChatFlashList } from "@/components/drawer/DrawerChatFlashList";
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

export function ConversationList(_props: unknown) {
  const { token } = useAuth();
  const { isOpen } = useDrawer();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeConversationListStyles(theme), [theme]);
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

  const highlightedIds = searchOpen ? matchingChatIds : undefined;

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
      <DrawerNavLinks
        styles={s}
        theme={theme}
        showIndicator={showIndicator}
        unseenCount={unseenCount}
        onProjects={openProjects}
        onLists={openLists}
        onReminders={openReminders}
      />
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
      <DrawerChatFlashList
        groups={groups}
        activeChatCount={allChats.length}
        loading={loading}
        error={error}
        isSectionCollapsed={isSectionCollapsed}
        toggleSectionCollapsed={toggleSectionCollapsed}
        highlightedIds={highlightedIds}
        onOpenChat={(id) => openChat(id)}
        onShowRowMenu={onShowRowMenu}
        listHeader={listHeader}
        contentPaddingTop={topInset}
        contentPaddingBottom={bottomInset}
        refreshing={refreshing}
        onRefresh={handleRefresh}
      />

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

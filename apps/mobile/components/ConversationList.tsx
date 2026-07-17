import { useCallback, useMemo } from "react";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { LinearGradient } from "expo-linear-gradient";
import { closeDrawer, startNewChatGlobal } from "@/lib/drawer";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useTheme } from "@/lib/theme";
import { ActionBanner } from "@/components/ActionBanner";
import { ChatActionsSheet } from "@/components/ChatActionsSheet";
import { ChatRenameSheet } from "@/components/ChatRenameSheet";
import { useAuth } from "@/contexts/AuthContext";
import { useDrawer } from "@/contexts/DrawerContext";
import { useChatBulkActions } from "@/hooks/useChatBulkActions";
import { useChatMenuActions } from "@/hooks/useChatMenuActions";
import { useDrawerChatList } from "@/hooks/useDrawerChatList";
import { useDrawerChatSelection } from "@/hooks/useDrawerChatSelection";
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
import { chatsFromSelection } from "@/lib/drawerChatSelection";
import { DrawerChatFlashList } from "@/components/drawer/DrawerChatFlashList";
import { DrawerListHeader } from "@/components/drawer/DrawerListHeader";
import { DrawerFooter } from "@/components/drawer/DrawerFooter";
import { DrawerHeader } from "@/components/drawer/DrawerHeader";
import { DrawerSelectionBar } from "@/components/drawer/DrawerSelectionBar";
import {
  FADE_EXTRA,
  FOOTER_CHROME,
  makeConversationListStyles,
  TOP_CHROME,
} from "@/components/drawer/conversationListStyles";

export function ConversationList(_props: unknown) {
  const { token } = useAuth();
  const { isOpen } = useDrawer();
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
    hasMore,
    loadingMore,
    loadMore,
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
    insertChatInGroups,
    isSectionCollapsed,
    toggleSectionCollapsed,
    moveChatPinState,
    moveChatArchiveState,
    removeChatFromGroupsById,
  } = useDrawerChatList({ token, isDrawerOpen: isOpen });

  const {
    menuChat,
    renameVisible,
    renameText,
    setRenameText,
    actionBanner,
    dismissActionBanner,
    showActionBanner,
    closeMenu,
    showRowMenu,
    handleShareChat,
    openRenameFromMenu,
    confirmRename,
    togglePinChat,
    toggleArchiveChat,
    confirmDeleteChat,
    requestDeleteChat,
    closeRename,
  } = useChatMenuActions({
    token,
    isDrawerOpen: isOpen,
    patchChatInGroups,
    insertChatInGroups,
    moveChatPinState,
    moveChatArchiveState,
    removeChatFromGroupsById,
  });

  const { bulkArchiveChats, bulkDeleteChats } = useChatBulkActions({
    token,
    insertChatInGroups,
    moveChatArchiveState,
    removeChatFromGroupsById,
    reloadChats: () => void load(),
    showActionBanner,
  });

  const {
    selectionMode,
    selectedIds,
    selectedCount,
    enterSelectionMode,
    exitSelectionMode,
    toggleSelected,
    selectAllListed,
  } = useDrawerChatSelection({
    isDrawerOpen: isOpen,
    listedChats: allChats,
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

  const onDeleteChat = useCallback(
    (chat: Chat) => {
      tap();
      requestDeleteChat(chat);
    },
    [requestDeleteChat],
  );

  const selectedChats = useMemo(
    () => chatsFromSelection(groups, selectedIds),
    [groups, selectedIds],
  );

  const handleBulkArchive = useCallback(() => {
    tap();
    bulkArchiveChats(selectedChats, exitSelectionMode);
  }, [bulkArchiveChats, selectedChats, exitSelectionMode]);

  const handleBulkDelete = useCallback(() => {
    tap();
    bulkDeleteChats(selectedChats, exitSelectionMode);
  }, [bulkDeleteChats, selectedChats, exitSelectionMode]);

  const handleEnterSelection = useCallback(() => {
    tap();
    closeSearch();
    enterSelectionMode();
  }, [closeSearch, enterSelectionMode]);

  const topInset = insets.top + 8 + TOP_CHROME;
  const bottomInset = insets.bottom + 8 + FOOTER_CHROME;
  const topFadeHeight = topInset + FADE_EXTRA;
  const bottomFadeHeight = bottomInset + FADE_EXTRA;

  const highlightedIds = searchOpen ? matchingChatIds : undefined;

  const listHeader = (
    <DrawerListHeader
      styles={s}
      theme={theme}
      showIndicator={showIndicator}
      unseenCount={unseenCount}
      onProjects={openProjects}
      onLists={openLists}
      onReminders={openReminders}
      loading={loading}
      error={error}
      activeChatCount={allChats.length}
      searchOpen={searchOpen}
      onRetry={() => void load()}
      hasSearchQuery={hasSearchQuery}
      searchLoading={searchLoading}
      searchError={searchError}
      searchResultCount={searchResults.length}
    />
  );

  const topFadeColors = topChromeFadeColors(theme);
  const bottomFadeColors = bottomChromeFadeColors(theme);

  return (
    <GestureHandlerRootView style={s.root}>
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
        placement="menu"
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
        onOpenChat={openChat}
        onShowRowMenu={onShowRowMenu}
        onDeleteChat={onDeleteChat}
        selectionMode={selectionMode}
        selectedIds={selectedIds}
        onToggleSelect={toggleSelected}
        listHeader={listHeader}
        contentPaddingTop={topInset}
        contentPaddingBottom={bottomInset}
        refreshing={refreshing}
        onRefresh={handleRefresh}
        searchOpen={searchOpen}
        searchResults={searchResults}
        searchHasMore={hasMore}
        searchLoadingMore={loadingMore}
        onSearchLoadMore={loadMore}
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
        selectionMode={selectionMode}
        selectedCount={selectedCount}
        onEnterSelection={handleEnterSelection}
        onExitSelection={exitSelectionMode}
        onSelectAll={selectAllListed}
      />

      {selectionMode ? (
        <DrawerSelectionBar
          styles={s}
          theme={theme}
          paddingBottom={insets.bottom + 8}
          selectedCount={selectedCount}
          onArchive={handleBulkArchive}
          onDelete={handleBulkDelete}
        />
      ) : (
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
      )}
    </GestureHandlerRootView>
  );
}

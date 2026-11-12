import { useCallback, useMemo, useState } from "react";
import { View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { clearChatHighlightGlobal, closeDrawer, getActiveChatIdGlobal } from "@/features/chat/drawer/drawer";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useTheme } from "@/lib/theme";
import { ActionBanner } from "@/ui/feedback/ActionBanner";
import { ChatActionsMenu } from "@/features/chat/components/ChatActionsMenu";
import { ChatRenameSheet } from "@/features/chat/components/ChatRenameSheet";
import { useAuthToken } from "@/contexts/AuthContext";
import { useDrawerOpen } from "@/contexts/DrawerContext";
import { useChatBulkActions } from "@/features/chat/hooks/useChatBulkActions";
import { useChatMenuActions } from "@/features/chat/hooks/useChatMenuActions";
import { useDrawerChatList } from "@/features/chat/drawer/useDrawerChatList";
import { useDrawerChatSelection } from "@/features/chat/drawer/useDrawerChatSelection";
import { useDrawerNavigation } from "@/features/chat/drawer/useDrawerNavigation";
import { useReminderBadgeCount } from "@/features/todos/hooks/useReminderBadgeCount";
import { useDrawerSearch } from "@/features/search/hooks/useDrawerSearch";
import { Chat } from "@/lib/api";
import {
  bottomChromeFadeColors,
  BOTTOM_CHROME_FADE_LOCATIONS,
  drawerHeaderFade,
} from "@/features/chat/components/chromeFade";
import { tap } from "@/lib/haptics";
import { useKeyboardHeight } from "@/ui/hooks/useKeyboardHeight";
import { chatsFromSelection, selectableChats } from "@/features/chat/drawer/drawerChatSelection";
import { ChatRowActions } from "@/features/chat/drawer/ConversationRow";
import { DrawerChatFlashList } from "@/features/chat/drawer/DrawerChatFlashList";
import { DrawerListHeader } from "@/features/chat/drawer/DrawerListHeader";
import { DrawerFooter } from "@/features/chat/drawer/DrawerFooter";
import { DrawerHeader } from "@/features/chat/drawer/DrawerHeader";
import { DrawerNavLinks } from "@/features/chat/drawer/DrawerNavLinks";
import { DrawerSelectionBar } from "@/features/chat/drawer/DrawerSelectionBar";
import {
  FADE_EXTRA,
  FOOTER_CHROME,
  makeConversationListStyles,
  TOP_CHROME,
} from "@/features/chat/drawer/conversationListStyles";

/** A row's long-press: its menu opens where the finger was. */
function useRowMenuAt(showRowMenu: (chat: Chat) => void) {
  const [menuPoint, setMenuPoint] = useState<{ x: number; y: number } | null>(null);
  const onShowRowMenu = useCallback(
    (chat: Chat, point: { x: number; y: number }) => {
      tap();
      setMenuPoint(point);
      showRowMenu(chat);
    },
    [showRowMenu],
  );
  return { menuPoint, onShowRowMenu };
}

export function ConversationList() {
  const token = useAuthToken();
  const isOpen = useDrawerOpen();
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
    loadingMoreError,
    loadMore,
    retrySearch,
    isCurrentSearch,
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
    moveChatArchiveState,
    removeChatFromGroupsById,
    hasOlderChats,
    loadOlderChats,
    hasMoreArchived,
    loadMoreArchivedChats,
    archivedPaging,
  } = useDrawerChatList({ isDrawerOpen: isOpen });

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
    openShareChat,
    exportChatPdf,
    openRenameFromMenu,
    confirmRename,
    togglePinChat,
    toggleArchiveChat,
    confirmDeleteChat,
    closeRename,
    rowAction,
  } = useChatMenuActions({
    token,
    isDrawerOpen: isOpen,
    patchChatInGroups,
    insertChatInGroups,
    removeChatFromGroupsById,
  });

  const { bulkArchiveChats, bulkDeleteChats } = useChatBulkActions({
    token,
    isDrawerOpen: isOpen,
    patchChatInGroups,
    insertChatInGroups,
    moveChatArchiveState,
    removeChatFromGroupsById,
    reloadChats: () => void load(false, true),
    showActionBanner,
  });

  const listedChats = useMemo(() => [...allChats, ...groups.archived], [allChats, groups.archived]);
  // "Select all" picks what is on screen: it used to take archived chats and collapsed sections too.
  const selectable = useMemo(
    () => selectableChats(groups, isSectionCollapsed),
    [groups, isSectionCollapsed],
  );

  const {
    selectionMode,
    selectedIds,
    selectedCount,
    enterSelectionMode,
    exitSelectionMode,
    toggleSelected,
    selectAllListed,
  } = useDrawerChatSelection({
    token,
    isDrawerOpen: isOpen,
    listedChats,
    selectableChats: selectable,
  });

  const { unseenCount, showIndicator } = useReminderBadgeCount({
    enabled: Boolean(token),
  });

  const openChat = useCallback(
    (id: string, messageId?: string | null) => {
      clearChatHighlightGlobal();
      closeDrawer();
      closeSearch();
      router.setParams({
        chatId: id,
        ...(messageId ? { highlightMessage: messageId } : { highlightMessage: undefined }),
      });
    },
    [closeSearch, router],
  );

  const openSearchResult = useCallback(
    (id: string, messageId?: string | null) => {
      if (isCurrentSearch()) openChat(id, messageId);
    },
    [isCurrentSearch, openChat],
  );

  const { newChat, openSettings, openReminders, openGallery } = useDrawerNavigation(token);

  const { menuPoint, onShowRowMenu } = useRowMenuAt(showRowMenu);

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

  const handleSelectFromMenu = useCallback(() => {
    const chatId = menuChat?.id;
    closeMenu();
    closeSearch();
    if (chatId) enterSelectionMode(chatId);
  }, [menuChat?.id, closeMenu, closeSearch, enterSelectionMode]);

  // Only the top bar (Recall, search) and the bottom bar (account, new chat) are fixed;
  // To-do scrolls with the titles.
  const topInset = insets.top + 8 + TOP_CHROME;
  // While search types, the keyboard covers the bottom bar: the results end just above
  // the keyboard, not a bar's height higher.
  const searchKeyboard = useKeyboardHeight(searchOpen);
  const bottomInset = searchKeyboard > 0 ? searchKeyboard + 8 : insets.bottom + 8 + FOOTER_CHROME;
  const topFadeHeight = topInset + FADE_EXTRA;
  const bottomFadeHeight = bottomInset + FADE_EXTRA;

  // Snapshot when the drawer opens — isOpen flip re-renders this list.
  const activeChatId = isOpen ? getActiveChatIdGlobal() : null;

  const onRetryLoad = useCallback(() => {
    void load(false, true);
  }, [load]);

  const listHeader = useMemo(
    () => (
      <>
        <DrawerNavLinks
          styles={s}
          showIndicator={showIndicator}
          unseenCount={unseenCount}
          onReminders={openReminders}
          onGallery={openGallery}
        />
        <DrawerListHeader
          loading={loading}
          error={error}
          activeChatCount={allChats.length}
          searchOpen={searchOpen}
          onRetry={onRetryLoad}
          onRetrySearch={retrySearch}
          hasSearchQuery={hasSearchQuery}
          searchLoading={searchLoading}
          searchError={searchError}
          searchResultCount={searchResults.length}
        />
      </>
    ),
    [
      s,
      showIndicator,
      unseenCount,
      openReminders,
      openGallery,
      loading,
      error,
      allChats.length,
      searchOpen,
      onRetryLoad,
      retrySearch,
      hasSearchQuery,
      searchLoading,
      searchError,
      searchResults.length,
    ],
  );

  const topFade = drawerHeaderFade(theme, insets.top + 8, topInset, topFadeHeight);
  const bottomFadeColors = bottomChromeFadeColors(theme);

  return (
    <View style={s.root}>
      <ChatActionsMenu
        visible={menuChat != null}
        anchorPoint={menuPoint}
        title={menuChat?.title ?? null}
        pinned={menuChat?.pinned ?? false}
        archived={menuChat?.archived ?? false}
        onClose={closeMenu}
        onShare={openShareChat}
        onExportPdf={exportChatPdf}
        onRename={openRenameFromMenu}
        onTogglePin={() => void togglePinChat()}
        onToggleArchive={() => void toggleArchiveChat()}
        onDelete={confirmDeleteChat}
        onSelectChats={handleSelectFromMenu}
      />
      <ChatRenameSheet
        visible={renameVisible}
        value={renameText}
        onChangeText={setRenameText}
        onClose={closeRename}
        onSave={() => void confirmRename()}
      />
      <ChatRowActions.Provider value={rowAction}>
        <DrawerChatFlashList
          groups={groups}
          activeChatCount={allChats.length}
          loading={loading}
          error={error}
          isSectionCollapsed={isSectionCollapsed}
          toggleSectionCollapsed={toggleSectionCollapsed}
          activeChatId={activeChatId}
          onOpenChat={openChat}
          onOpenSearchResult={openSearchResult}
          onShowRowMenu={onShowRowMenu}
          selectionMode={selectionMode}
          selectedIds={selectedIds}
          onToggleSelect={toggleSelected}
          listHeader={listHeader}
          contentPaddingTop={topInset}
          contentPaddingBottom={bottomInset}
          refreshing={refreshing}
          onRefresh={handleRefresh}
          searchOpen={searchOpen}
          searching={searchOpen && hasSearchQuery}
          searchQuery={searchQuery}
          searchResults={searchResults}
          searchHasMore={hasMore}
          searchLoadingMore={loadingMore}
          searchLoadingMoreError={loadingMoreError}
          onSearchLoadMore={loadMore}
          onLoadOlderChats={hasOlderChats ? loadOlderChats : undefined}
          onLoadMoreArchived={hasMoreArchived ? loadMoreArchivedChats : undefined}
          archivedPaging={archivedPaging}
        />
      </ChatRowActions.Provider>

      <LinearGradient
        colors={topFade.colors}
        locations={topFade.locations}
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
        onExitSelection={exitSelectionMode}
        onSelectAll={selectAllListed}
      />

      {selectionMode ? (
        <DrawerSelectionBar
          styles={s}
          theme={theme}
          paddingBottom={insets.bottom + 8}
          selectedCount={selectedCount}
          archivableCount={selectedChats.filter((chat) => !chat.archived).length}
          onArchive={handleBulkArchive}
          onDelete={handleBulkDelete}
        />
      ) : (
        <DrawerFooter
          styles={s}
          theme={theme}
          paddingBottom={insets.bottom + 8}
          onAccount={openSettings}
          onNewChat={newChat}
        />
      )}

      <ActionBanner
        message={actionBanner?.message ?? null}
        icon={actionBanner?.icon}
        bottomOffset={FOOTER_CHROME + 16}
        onDismiss={dismissActionBanner}
      />
    </View>
  );
}

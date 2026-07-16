import { useCallback, useMemo } from "react";
import { Pressable, RefreshControl, Text } from "react-native";
import { FlashList } from "@shopify/flash-list";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { StateView } from "@/components/StateView";
import {
  ConversationRow,
  makeConversationRowStyles,
} from "@/components/drawer/ConversationRow";
import { makeConversationListStyles } from "@/components/drawer/conversationListStyles";
import {
  ARCHIVED_CHAT_SECTION,
  CHAT_DATE_SECTIONS,
  drawerSectionTitleKey,
  isCollapsibleChatSection,
  PINNED_CHAT_SECTION,
  type ChatListSectionKey,
} from "@/lib/chatListSections";
import { isChatTitleGenerating } from "@/lib/drawer";
import { Chat, ChatList } from "@/lib/api";
import { useTheme } from "@/lib/theme";

export type DrawerChatListItem =
  | {
      type: "sectionHeader";
      key: ChatListSectionKey;
      title: string;
      count: number;
      collapsible: boolean;
    }
  | { type: "row"; key: string; chat: Chat };

type Props = {
  groups: ChatList;
  activeChatCount: number;
  loading: boolean;
  error: boolean;
  isSectionCollapsed: (key: ChatListSectionKey) => boolean;
  toggleSectionCollapsed: (key: ChatListSectionKey) => void;
  highlightedIds?: Set<string>;
  onOpenChat: (id: string) => void;
  onShowRowMenu: (chat: Chat) => void;
  onDeleteChat: (chat: Chat) => void;
  selectionMode?: boolean;
  selectedIds?: ReadonlySet<string>;
  onToggleSelect?: (chatId: string) => void;
  listHeader: React.ReactElement;
  contentPaddingTop: number;
  contentPaddingBottom: number;
  refreshing: boolean;
  onRefresh: () => void;
};

export function DrawerChatFlashList({
  groups,
  activeChatCount,
  loading,
  error,
  isSectionCollapsed,
  toggleSectionCollapsed,
  highlightedIds,
  onOpenChat,
  onShowRowMenu,
  onDeleteChat,
  selectionMode = false,
  selectedIds,
  onToggleSelect,
  listHeader,
  contentPaddingTop,
  contentPaddingBottom,
  refreshing,
  onRefresh,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeConversationListStyles(theme), [theme]);
  const rowStyles = useMemo(() => makeConversationRowStyles(theme), [theme]);

  const chatListData = useMemo<DrawerChatListItem[]>(() => {
    if (activeChatCount === 0 && groups.archived.length === 0) return [];
    const items: DrawerChatListItem[] = [];
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
  }, [activeChatCount, groups, isSectionCollapsed, t]);

  const renderChatItem = useCallback(
    ({ item }: { item: DrawerChatListItem }) => {
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
          onOpen={onOpenChat}
          onLongPress={onShowRowMenu}
          onDelete={selectionMode ? undefined : onDeleteChat}
          selectionMode={selectionMode}
          selected={selectedIds?.has(item.chat.id) ?? false}
          onToggleSelect={onToggleSelect}
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
      onOpenChat,
      onShowRowMenu,
      onDeleteChat,
      selectionMode,
      selectedIds,
      onToggleSelect,
    ],
  );

  const listEmpty =
    activeChatCount === 0 && !loading && !error ? (
      <StateView variant="empty" compact message={t("drawer.no_conversations")} />
    ) : null;

  return (
    <FlashList
      style={s.list}
      data={chatListData}
      renderItem={renderChatItem}
      keyExtractor={(item) => item.key}
      getItemType={(item) => item.type}
      showsVerticalScrollIndicator={false}
      contentContainerStyle={{
        paddingTop: contentPaddingTop,
        paddingBottom: contentPaddingBottom,
      }}
      keyboardShouldPersistTaps="handled"
      ListHeaderComponent={listHeader}
      ListEmptyComponent={listEmpty}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onRefresh}
          colors={[theme.primary]}
          tintColor={theme.primary}
        />
      }
    />
  );
}

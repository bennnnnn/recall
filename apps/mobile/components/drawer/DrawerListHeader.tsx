import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { DrawerNavLinks } from "@/components/drawer/DrawerNavLinks";
import { DrawerSearchResults } from "@/components/drawer/DrawerSearchResults";
import type { ConversationListStyles } from "@/components/drawer/conversationListStyles";
import type { SearchResult } from "@/lib/api";
import type { Theme } from "@/lib/theme";

type Props = {
  styles: ConversationListStyles;
  theme: Theme;
  showIndicator: boolean;
  unseenCount: number;
  onProjects: () => void;
  onLists: () => void;
  onReminders: () => void;
  loading: boolean;
  error: boolean;
  activeChatCount: number;
  searchOpen: boolean;
  onRetry: () => void;
  hasSearchQuery: boolean;
  searchLoading: boolean;
  searchError: boolean;
  searchResults: SearchResult[];
  onOpenChat: (chatId: string, messageId?: string | null) => void;
};

export function DrawerListHeader({
  styles: s,
  theme,
  showIndicator,
  unseenCount,
  onProjects,
  onLists,
  onReminders,
  loading,
  error,
  activeChatCount,
  searchOpen,
  onRetry,
  hasSearchQuery,
  searchLoading,
  searchError,
  searchResults,
  onOpenChat,
}: Props) {
  const { t } = useTranslation();

  return (
    <>
      <DrawerNavLinks
        styles={s}
        theme={theme}
        showIndicator={showIndicator}
        unseenCount={unseenCount}
        onProjects={onProjects}
        onLists={onLists}
        onReminders={onReminders}
      />
      {loading && activeChatCount === 0 && !searchOpen ? (
        <View style={s.inlineEmpty}>
          <ActivityIndicator color={theme.primary} />
        </View>
      ) : error && activeChatCount === 0 ? (
        <View style={s.inlineEmpty}>
          <Ionicons
            name="cloud-offline-outline"
            size={36}
            color={theme.textTertiary}
          />
          <Text style={s.emptyText}>{t("drawer.cant_reach")}</Text>
          <Pressable style={s.retryBtn} onPress={onRetry}>
            <Text style={s.retryText}>{t("common.retry")}</Text>
          </Pressable>
        </View>
      ) : null}
      {searchOpen ? (
        <DrawerSearchResults
          hasSearchQuery={hasSearchQuery}
          searchLoading={searchLoading}
          searchError={searchError}
          searchResults={searchResults}
          onOpenChat={onOpenChat}
        />
      ) : null}
    </>
  );
}

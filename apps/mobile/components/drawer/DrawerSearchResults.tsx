import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { displayChatTitle } from "@/lib/chatTitle";
import { Theme, useTheme } from "@/lib/theme";
import type { SearchResult } from "@/lib/api";

type Props = {
  hasSearchQuery: boolean;
  searchLoading: boolean;
  searchError: boolean;
  searchResults: SearchResult[];
  onOpenChat: (chatId: string, messageId?: string | null) => void;
};

export function DrawerSearchResults({
  hasSearchQuery,
  searchLoading,
  searchError,
  searchResults,
  onOpenChat,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = makeStyles(theme);

  return (
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
              result.message_id ? result.message_id : `title-${result.chat_id}`
            }
            style={s.searchResult}
            onPress={() => onOpenChat(result.chat_id, result.message_id)}
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
                color={
                  result.match_type === "title" ? theme.primary : theme.textSecondary
                }
              />
              <Text style={s.searchResultTitle} numberOfLines={1}>
                {displayChatTitle(result.chat_title, {}, t)}
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
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    section: { marginBottom: 8 },
    sectionTitle: {
      fontSize: 11,
      fontWeight: "700",
      color: theme.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.8,
      paddingHorizontal: 14,
      paddingTop: 12,
      paddingBottom: 6,
    },
    searchHint: {
      fontSize: 14,
      color: theme.textSecondary,
      paddingHorizontal: 14,
      paddingVertical: 12,
    },
    searchStatus: { paddingVertical: 16, alignItems: "center" },
    searchResult: {
      paddingHorizontal: 14,
      paddingVertical: 12,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: theme.border,
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
    },
    searchResultSnippet: { fontSize: 15, lineHeight: 21, color: theme.text },
  });
}

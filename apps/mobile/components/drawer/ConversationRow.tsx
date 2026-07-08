import { memo } from "react";
import { Pressable, StyleSheet, Text, View, ViewStyle, TextStyle } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { Theme, useTheme } from "@/lib/theme";
import type { Chat } from "@/lib/api";
import { displayChatTitle } from "@/lib/chatTitle";

export type ConversationRowStyles = {
  row: ViewStyle;
  rowIcon: ViewStyle;
  title: TextStyle;
  titlePending: TextStyle;
  rowHighlighted: ViewStyle;
};

type Props = {
  chat: Chat;
  /**
   * Stable callbacks (e.g. the useCallback-wrapped onOpenChat/onShowRowMenu
   * from the parent), not a per-row closure — this row is memoized, and a
   * fresh `() => onOpen(chatId)` created on every renderItem call would
   * defeat that by changing the onOpen prop's identity every render.
   */
  onOpen: (chatId: string) => void;
  onLongPress: (chat: Chat) => void;
  highlighted?: boolean;
  titleGenerating?: boolean;
  rowStyles: ConversationRowStyles;
};

export const ConversationRow = memo(function ConversationRow({
  chat,
  onOpen,
  onLongPress,
  highlighted = false,
  titleGenerating = false,
  rowStyles: r,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const label = displayChatTitle(chat.title, { generating: titleGenerating }, t);
  return (
    <Pressable
      style={[r.row, highlighted && r.rowHighlighted]}
      onPress={() => onOpen(chat.id)}
      onLongPress={() => onLongPress(chat)}
    >
      {chat.pinned ? (
        <View style={r.rowIcon}>
          <Ionicons name="bookmark" size={16} color={theme.primary} />
        </View>
      ) : null}
      <Text
        style={[r.title, titleGenerating && !chat.title && r.titlePending]}
        numberOfLines={1}
      >
        {label}
      </Text>
    </Pressable>
  );
});

export function makeConversationRowStyles(theme: Theme): ConversationRowStyles {
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
    titlePending: { color: theme.textTertiary, fontStyle: "italic" },
    rowHighlighted: {
      backgroundColor: theme.primaryLight,
      borderRadius: 10,
      marginHorizontal: 6,
      paddingHorizontal: 8,
    },
  });
}

import { memo } from "react";
import { Pressable, StyleSheet, Text, View, ViewStyle, TextStyle } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { Theme, useTheme } from "@/lib/theme";
import type { Chat } from "@/lib/api";
import { displayChatTitle } from "@/lib/chat/chatTitle";

export type ConversationRowStyles = {
  row: ViewStyle;
  rowIcon: ViewStyle;
  title: TextStyle;
  titlePending: TextStyle;
  titleActive: TextStyle;
  rowHighlighted: ViewStyle;
  rowActive: ViewStyle;
  rowSelected: ViewStyle;
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
  selectionMode?: boolean;
  selected?: boolean;
  onToggleSelect?: (chatId: string) => void;
  highlighted?: boolean;
  /** Currently open chat on the home screen. */
  active?: boolean;
  titleGenerating?: boolean;
  rowStyles: ConversationRowStyles;
};

export const ConversationRow = memo(function ConversationRow({
  chat,
  onOpen,
  onLongPress,
  selectionMode = false,
  selected = false,
  onToggleSelect,
  highlighted = false,
  active = false,
  titleGenerating = false,
  rowStyles: r,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const label = displayChatTitle(chat.title, { generating: titleGenerating }, t);

  return (
    <Pressable
      style={[
        r.row,
        highlighted && r.rowHighlighted,
        active && !selectionMode && r.rowActive,
        selected && r.rowSelected,
      ]}
      onPress={() => {
        if (selectionMode) onToggleSelect?.(chat.id);
        else onOpen(chat.id);
      }}
      onLongPress={() => {
        if (selectionMode) onToggleSelect?.(chat.id);
        else onLongPress(chat);
      }}
      accessibilityRole={selectionMode ? "checkbox" : "button"}
      accessibilityLabel={label}
      accessibilityState={
        selectionMode ? { checked: selected } : { selected: active }
      }
    >
      {selectionMode ? (
        <View style={r.rowIcon}>
          <Icon
            name={selected ? "checkbox" : "square-outline"}
            size={20}
            color={selected ? theme.primary : theme.textTertiary}
          />
        </View>
      ) : chat.pinned ? (
        <View style={r.rowIcon}>
          <Icon name="bookmark" size={16} color={theme.primary} />
        </View>
      ) : null}
      <Text
        style={[
          r.title,
          titleGenerating && !chat.title && r.titlePending,
          active && !selectionMode && r.titleActive,
        ]}
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
    // Wash already signals active — keep ink on theme.text, just bolder.
    titleActive: { fontWeight: "700" },
    rowHighlighted: {
      backgroundColor: theme.primaryLight,
      borderRadius: 10,
      marginHorizontal: 6,
      paddingHorizontal: 8,
    },
    rowActive: {
      backgroundColor: theme.surfaceAlt,
      borderRadius: 10,
      marginHorizontal: 6,
      paddingHorizontal: 8,
    },
    rowSelected: {
      backgroundColor: theme.primaryLight,
    },
  });
}

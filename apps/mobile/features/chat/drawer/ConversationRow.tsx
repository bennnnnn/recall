import { createContext, memo, useContext } from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  View,
  ViewStyle,
  TextStyle,
  type AccessibilityActionInfo,
} from "react-native";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";

import { Icon } from "@/ui/icons/Icon";
import { Theme, useTheme } from "@/lib/theme";
import { Italic, Type, Weight } from "@/lib/type";
import type { Chat } from "@/lib/api";
import { displayChatTitle } from "@/features/chat/model/title";
import type { ChatRowAction } from "@/features/chat/hooks/useChatMenuActions";
import { IconSize } from "@/ui/icons/sizes";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";

type ConversationRowStyles = {
  row: ViewStyle;
  rowIcon: ViewStyle;
  title: TextStyle;
  titlePending: TextStyle;
  titleActive: TextStyle;
  rowActive: ViewStyle;
  rowSelected: ViewStyle;
  rowPressed: ViewStyle;
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
  /** `point` is where the finger was, so the row menu opens there. */
  onLongPress: (chat: Chat, point: { x: number; y: number }) => void;
  selectionMode?: boolean;
  selected?: boolean;
  onToggleSelect?: (chatId: string) => void;
  /** Currently open chat on the home screen. */
  active?: boolean;
  titleGenerating?: boolean;
  rowStyles: ConversationRowStyles;
};

/**
 * Runs a screen reader's action on a row (the drawer's `rowAction`). One handler for every row,
 * so a row redraws only when its own chat does.
 */
export const ChatRowActions = createContext<((chat: Chat, action: ChatRowAction) => void) | null>(null);

/**
 * The long-press menu's actions, offered to a screen reader on the row itself: they were
 * reached only by a long-press, where the Library's tiles list theirs. Select stays in the menu.
 */
function rowActions(chat: Chat, t: TFunction): AccessibilityActionInfo[] {
  const actions: AccessibilityActionInfo[] = [
    { name: "share", label: t("chat.share") },
    { name: "rename", label: t("chat.rename") },
  ];
  if (!chat.archived) actions.push({ name: "pin", label: t(chat.pinned ? "chat.unpin" : "chat.pin") });
  actions.push(
    { name: "archive", label: t(chat.archived ? "chat.unarchive" : "chat.archive") },
    { name: "delete", label: t("common.delete") },
  );
  return actions;
}

export const ConversationRow = memo(function ConversationRow({
  chat,
  onOpen,
  onLongPress,
  selectionMode = false,
  selected = false,
  onToggleSelect,
  active = false,
  titleGenerating = false,
  rowStyles: r,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const label = displayChatTitle(chat.title, { generating: titleGenerating }, t);
  const onAction = useContext(ChatRowActions);

  return (
    <Pressable
      style={({ pressed }) => [
        r.row,
        active && !selectionMode && r.rowActive,
        selected && r.rowSelected,
        pressed && r.rowPressed,
      ]}
      onPress={() => {
        if (selectionMode) onToggleSelect?.(chat.id);
        else onOpen(chat.id);
      }}
      onLongPress={(event) => {
        if (selectionMode) onToggleSelect?.(chat.id);
        else onLongPress(chat, { x: event.nativeEvent.pageX, y: event.nativeEvent.pageY });
      }}
      accessibilityRole={selectionMode ? "checkbox" : "button"}
      accessibilityLabel={label}
      accessibilityState={
        selectionMode ? { checked: selected } : { selected: active }
      }
      accessibilityActions={selectionMode || !onAction ? undefined : rowActions(chat, t)}
      onAccessibilityAction={(event) => onAction?.(chat, event.nativeEvent.actionName as ChatRowAction)}
    >
      {selectionMode ? (
        <View style={r.rowIcon}>
          <Icon
            name={selected ? "checkbox-checked" : "square"}
            size={IconSize.sm}
            color={selected ? theme.primary : theme.textTertiary}
          />
        </View>
      ) : chat.pinned ? (
        <View style={r.rowIcon}>
          <Icon name="bookmark" size={IconSize.xs} color={theme.primary} />
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
      minHeight: 44,
      paddingVertical: Space.sm,
      paddingHorizontal: Space.md,
      gap: Space.sm,
    },
    rowIcon: { flexShrink: 0 },
    title: { flex: 1, ...Type.body, ...Weight.medium, color: theme.text },
    titlePending: { color: theme.textTertiary, ...Italic.regular },
    // Wash already signals active — keep ink on theme.text, just bolder.
    titleActive: { ...Weight.bold },
    rowActive: {
      backgroundColor: theme.surfaceAlt,
      borderRadius: Radius.sm,
      marginHorizontal: Space.xs,
      paddingHorizontal: Space.xs,
    },
    rowSelected: {
      backgroundColor: theme.primaryLight,
    },
    rowPressed: { opacity: 0.72 },
  });
}

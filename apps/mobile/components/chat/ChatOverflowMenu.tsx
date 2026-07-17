import { useMemo, type ComponentProps } from "react";
import { Pressable, Text, View } from "react-native";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import {
  CHAT_OVERFLOW_MENU_INSET,
  makeChatOverflowMenuStyles,
} from "@/components/chat/chatOverflowMenuStyles";
import { CHAT_HEADER_BAR_HEIGHT } from "@/lib/chatComposerLogic";
import { useTheme } from "@/lib/theme";

type MciName = ComponentProps<typeof MaterialCommunityIcons>["name"];

type Props = {
  visible: boolean;
  title: string | null;
  pinned: boolean;
  archived?: boolean;
  /** Extra top offset below the status bar (defaults to chat header bar height). */
  headerBarHeight?: number;
  onClose: () => void;
  onShare: () => void;
  onRename: () => void;
  onTogglePin: () => void;
  onToggleArchive?: () => void;
  onDelete: () => void;
};

/**
 * Floating overflow menu shared by the chat header ⋮ and drawer long-press.
 * No Modal — keeps the keyboard open when opened from the composer.
 */
export function ChatOverflowMenu({
  visible,
  title,
  pinned,
  archived = false,
  headerBarHeight = CHAT_HEADER_BAR_HEIGHT,
  onClose,
  onShare,
  onRename,
  onTogglePin,
  onToggleArchive,
  onDelete,
}: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const insets = useSafeAreaInsets();
  const s = useMemo(() => makeChatOverflowMenuStyles(theme), [theme]);

  if (!visible) return null;

  const row = (
    icon: MciName,
    label: string,
    onPress: () => void,
    danger = false,
  ) => (
    <Pressable
      style={({ pressed }) => [s.item, pressed && s.itemPressed]}
      onPress={onPress}
    >
      <MaterialCommunityIcons
        name={icon}
        size={24}
        color={danger ? theme.danger : theme.text}
      />
      <Text style={[s.label, danger && s.labelDanger]}>{label}</Text>
    </Pressable>
  );

  return (
    <View style={s.root} pointerEvents="box-none" testID="chat-actions-menu">
      <Pressable
        style={s.backdrop}
        onPress={onClose}
        accessibilityRole="button"
        accessibilityLabel={t("common.cancel")}
        testID="chat-actions-menu-backdrop"
      />
      <View
        style={[
          s.panelShadow,
          {
            top: insets.top + headerBarHeight + CHAT_OVERFLOW_MENU_INSET.belowHeader,
            right: CHAT_OVERFLOW_MENU_INSET.right,
            left: CHAT_OVERFLOW_MENU_INSET.left,
          },
        ]}
      >
        <View style={s.panel}>
          {title ? (
            <Text style={s.title} numberOfLines={1}>
              {title}
            </Text>
          ) : null}
          <View style={s.rows}>
            {row("share-variant-outline", t("chat.share"), onShare)}
            {row(
              pinned ? "pin" : "pin-outline",
              pinned ? t("chat.unpin") : t("chat.pin"),
              onTogglePin,
            )}
            {row("pencil-outline", t("chat.rename"), onRename)}
            {onToggleArchive
              ? row(
                  archived ? "archive-arrow-up-outline" : "archive-outline",
                  archived ? t("chat.unarchive") : t("chat.archive"),
                  onToggleArchive,
                )
              : null}
            {row("trash-can-outline", t("common.delete"), onDelete, true)}
          </View>
        </View>
      </View>
    </View>
  );
}

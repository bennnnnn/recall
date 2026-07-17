import { useEffect, useMemo, useState, type ComponentProps } from "react";
import { Keyboard, Platform, Pressable, Text, View } from "react-native";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import {
  CHAT_OVERFLOW_MENU_INSET,
  makeChatOverflowMenuStyles,
} from "@/components/chat/chatOverflowMenuStyles";
import { useTheme } from "@/lib/theme";

type MciName = ComponentProps<typeof MaterialCommunityIcons>["name"];

type Props = {
  visible: boolean;
  title: string | null;
  pinned: boolean;
  archived?: boolean;
  onClose: () => void;
  onShare: () => void;
  onRename: () => void;
  onTogglePin: () => void;
  onToggleArchive?: () => void;
  onDelete: () => void;
};

/**
 * Floating overflow menu shared by the chat header ⋮ and drawer long-press.
 * Anchored to the bottom (thumb reach). No Modal — keyboard can stay open;
 * the card lifts above the keyboard when it is visible.
 */
export function ChatOverflowMenu({
  visible,
  title,
  pinned,
  archived = false,
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
  const [keyboardHeight, setKeyboardHeight] = useState(0);

  useEffect(() => {
    if (!visible) {
      setKeyboardHeight(0);
      return;
    }
    const showEvent = Platform.OS === "ios" ? "keyboardWillShow" : "keyboardDidShow";
    const hideEvent = Platform.OS === "ios" ? "keyboardWillHide" : "keyboardDidHide";
    const showSub = Keyboard.addListener(showEvent, (e) => {
      setKeyboardHeight(Math.max(0, e.endCoordinates.height));
    });
    const hideSub = Keyboard.addListener(hideEvent, () => setKeyboardHeight(0));
    // If the composer already has focus, pick up the current keyboard frame.
    const metrics = Keyboard.metrics();
    if (metrics?.height) setKeyboardHeight(metrics.height);
    return () => {
      showSub.remove();
      hideSub.remove();
    };
  }, [visible]);

  if (!visible) return null;

  const bottom =
    (keyboardHeight > 0 ? keyboardHeight : Math.max(insets.bottom, 8)) +
    CHAT_OVERFLOW_MENU_INSET.aboveBottom;

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
            bottom,
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

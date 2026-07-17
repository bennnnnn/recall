import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { CHAT_HEADER_BAR_HEIGHT } from "@/lib/chatComposerLogic";
import { Theme, useTheme } from "@/lib/theme";

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
  /**
   * `sheet` — bottom action sheet (drawer).
   * `menu` — top-right dropdown under the chat header ⋮; no Modal so the
   * keyboard can stay open.
   */
  placement?: "sheet" | "menu";
};

export function ChatActionsSheet({
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
  placement = "sheet",
}: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const insets = useSafeAreaInsets();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const isMenu = placement === "menu";
  // Menu: filled / social glyphs read bolder; sheet keeps lighter outlines.
  const iconSize = isMenu ? 22 : 20;
  const shareIcon = isMenu ? "share-social" : "share-outline";
  const renameIcon = isMenu ? "pencil" : "pencil-outline";
  const pinIcon = pinned ? "pin" : "pin-outline";
  const archiveIcon = archived
    ? isMenu
      ? "arrow-undo"
      : "arrow-undo-outline"
    : isMenu
      ? "archive"
      : "archive-outline";
  const trashIcon = isMenu ? "trash" : "trash-outline";

  const row = (
    icon: keyof typeof Ionicons.glyphMap,
    label: string,
    onPress: () => void,
    danger = false,
  ) => (
    <Pressable style={s.item} onPress={onPress}>
      <Ionicons
        name={icon}
        size={iconSize}
        color={danger ? theme.danger : theme.text}
      />
      <Text style={[s.label, danger && s.labelDanger]}>{label}</Text>
    </Pressable>
  );

  const actionRows = (
    <>
      {row(shareIcon, t("chat.share"), onShare)}
      {!isMenu ? <View style={s.divider} /> : null}
      {row(renameIcon, t("chat.rename"), onRename)}
      {!isMenu ? <View style={s.divider} /> : null}
      {row(pinIcon, pinned ? t("chat.unpin") : t("chat.pin"), onTogglePin)}
      {!isMenu ? <View style={s.divider} /> : null}
      {onToggleArchive ? (
        <>
          {row(
            archiveIcon,
            archived ? t("chat.unarchive") : t("chat.archive"),
            onToggleArchive,
          )}
          {!isMenu ? <View style={s.divider} /> : null}
        </>
      ) : null}
      {row(trashIcon, t("common.delete"), onDelete, true)}
    </>
  );

  if (isMenu) {
    if (!visible) return null;
    return (
      <View
        style={s.menuRoot}
        pointerEvents="box-none"
        testID="chat-actions-menu"
      >
        <Pressable
          style={s.menuBackdrop}
          onPress={onClose}
          accessibilityRole="button"
          accessibilityLabel={t("common.cancel")}
          testID="chat-actions-menu-backdrop"
        />
        {/* Outer wrapper keeps the shadow; inner clips rounded corners. */}
        <View
          style={[
            s.menuPanelShadow,
            {
              top: insets.top + CHAT_HEADER_BAR_HEIGHT + 4,
              right: 10,
              left: 56,
            },
          ]}
        >
          <View style={s.menuPanel}>
            {title ? (
              <Text style={s.menuTitle} numberOfLines={1}>
                {title}
              </Text>
            ) : null}
            {actionRows}
          </View>
        </View>
      </View>
    );
  }

  return (
    <AppSheet
      visible={visible}
      onClose={onClose}
      variant="bottom"
      withHandle
      minBottomPadding={12}
      contentContainerStyle={s.panel}
    >
      {title ? (
        <Text style={s.sheetTitle} numberOfLines={2}>
          {title}
        </Text>
      ) : null}
      <View style={s.group}>{actionRows}</View>
      <Pressable style={s.cancelBtn} onPress={onClose}>
        <Text style={s.cancelText}>{t("common.cancel")}</Text>
      </Pressable>
    </AppSheet>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    panel: {
      paddingHorizontal: 12,
      paddingTop: 8,
      gap: 10,
    },
    sheetTitle: {
      fontSize: 13,
      fontWeight: "600",
      color: C.textSecondary,
      textAlign: "center",
      paddingHorizontal: 16,
      marginBottom: 2,
    },
    group: {
      backgroundColor: C.surface,
      borderRadius: 14,
      overflow: "hidden",
    },
    menuRoot: {
      ...StyleSheet.absoluteFill,
      zIndex: 400,
      elevation: 24,
    },
    menuBackdrop: {
      ...StyleSheet.absoluteFill,
      backgroundColor: C.scrim,
    },
    menuPanelShadow: {
      position: "absolute",
      borderRadius: 14,
      // Shadow must live on a view without overflow:hidden or iOS clips it.
      backgroundColor: C.bg,
      shadowColor: "#000",
      shadowOpacity: C.isDark ? 0.55 : 0.28,
      shadowRadius: 20,
      shadowOffset: { width: 0, height: 10 },
      elevation: 20,
    },
    menuPanel: {
      borderRadius: 14,
      backgroundColor: C.bg,
      overflow: "hidden",
    },
    menuTitle: {
      fontSize: 13,
      fontWeight: "600",
      color: C.textSecondary,
      paddingHorizontal: 18,
      paddingTop: 14,
      paddingBottom: 6,
    },
    item: {
      flexDirection: "row",
      alignItems: "center",
      paddingHorizontal: 18,
      paddingVertical: 15,
      gap: 14,
    },
    label: { fontSize: 16, color: C.text, fontWeight: "400", flex: 1 },
    labelDanger: { color: C.danger },
    divider: {
      height: StyleSheet.hairlineWidth,
      backgroundColor: C.border,
      marginLeft: 52,
    },
    cancelBtn: {
      backgroundColor: C.surface,
      borderRadius: 14,
      paddingVertical: 16,
      alignItems: "center",
    },
    cancelText: { fontSize: 17, fontWeight: "600", color: C.primary },
  });
}

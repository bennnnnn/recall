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
  // Menu matches ChatGPT-style bold outlines; sheet keeps smaller outlines.
  const iconSize = isMenu ? 24 : 20;

  const row = (
    icon: keyof typeof Ionicons.glyphMap,
    label: string,
    onPress: () => void,
    danger = false,
  ) => (
    <Pressable
      style={({ pressed }) => [s.item, isMenu && pressed && s.itemPressed]}
      onPress={onPress}
    >
      <Ionicons
        name={icon}
        size={iconSize}
        color={danger ? theme.danger : theme.text}
      />
      <Text style={[isMenu ? s.menuLabel : s.label, danger && s.labelDanger]}>
        {label}
      </Text>
    </Pressable>
  );

  // ChatGPT order: Share → Pin → … → Archive → Delete. Keep Rename (ours).
  const actionRows = isMenu ? (
    <>
      {row("share-social-outline", t("chat.share"), onShare)}
      {row(pinned ? "pin" : "pin-outline", pinned ? t("chat.unpin") : t("chat.pin"), onTogglePin)}
      {row("pencil-outline", t("chat.rename"), onRename)}
      {onToggleArchive
        ? row(
            archived ? "arrow-undo-outline" : "archive-outline",
            archived ? t("chat.unarchive") : t("chat.archive"),
            onToggleArchive,
          )
        : null}
      {row("trash-outline", t("common.delete"), onDelete, true)}
    </>
  ) : (
    <>
      {row("share-outline", t("chat.share"), onShare)}
      <View style={s.divider} />
      {row("pencil-outline", t("chat.rename"), onRename)}
      <View style={s.divider} />
      {row(pinned ? "pin" : "pin-outline", pinned ? t("chat.unpin") : t("chat.pin"), onTogglePin)}
      <View style={s.divider} />
      {onToggleArchive ? (
        <>
          {row(
            archived ? "arrow-undo-outline" : "archive-outline",
            archived ? t("chat.unarchive") : t("chat.archive"),
            onToggleArchive,
          )}
          <View style={s.divider} />
        </>
      ) : null}
      {row("trash-outline", t("common.delete"), onDelete, true)}
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
              top: insets.top + CHAT_HEADER_BAR_HEIGHT + 6,
              right: 12,
              left: 44,
            },
          ]}
        >
          <View style={s.menuPanel}>
            {title ? (
              <Text style={s.menuTitle} numberOfLines={1}>
                {title}
              </Text>
            ) : null}
            <View style={s.menuRows}>{actionRows}</View>
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
      // Light dim so the chat stays readable under the card (ChatGPT-style).
      backgroundColor: C.isDark ? "rgba(0,0,0,0.45)" : "rgba(0,0,0,0.18)",
    },
    menuPanelShadow: {
      position: "absolute",
      borderRadius: 24,
      backgroundColor: C.bg,
      shadowColor: "#000",
      shadowOpacity: C.isDark ? 0.5 : 0.22,
      shadowRadius: 28,
      shadowOffset: { width: 0, height: 12 },
      elevation: 22,
    },
    menuPanel: {
      borderRadius: 24,
      backgroundColor: C.bg,
      overflow: "hidden",
      paddingBottom: 8,
    },
    menuTitle: {
      fontSize: 15,
      fontWeight: "500",
      color: C.textTertiary,
      paddingHorizontal: 20,
      paddingTop: 18,
      paddingBottom: 10,
    },
    menuRows: {
      paddingBottom: 6,
    },
    item: {
      flexDirection: "row",
      alignItems: "center",
      paddingHorizontal: 20,
      paddingVertical: 14,
      gap: 16,
    },
    itemPressed: {
      backgroundColor: C.surfaceAlt,
    },
    label: { fontSize: 16, color: C.text, fontWeight: "400", flex: 1 },
    menuLabel: {
      fontSize: 17,
      color: C.text,
      fontWeight: "500",
      flex: 1,
    },
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

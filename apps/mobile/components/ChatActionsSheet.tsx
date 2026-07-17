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

  const actionRows = (
    <>
      <Pressable style={s.item} onPress={onShare}>
        <Ionicons name="share-outline" size={20} color={theme.text} />
        <Text style={s.label}>{t("chat.share")}</Text>
      </Pressable>
      <View style={s.divider} />
      <Pressable style={s.item} onPress={onRename}>
        <Ionicons name="pencil-outline" size={20} color={theme.text} />
        <Text style={s.label}>{t("chat.rename")}</Text>
      </Pressable>
      <View style={s.divider} />
      <Pressable style={s.item} onPress={onTogglePin}>
        <Ionicons
          name={pinned ? "bookmark" : "bookmark-outline"}
          size={20}
          color={theme.text}
        />
        <Text style={s.label}>{pinned ? t("chat.unpin") : t("chat.pin")}</Text>
      </Pressable>
      <View style={s.divider} />
      {onToggleArchive ? (
        <>
          <Pressable style={s.item} onPress={onToggleArchive}>
            <Ionicons
              name={archived ? "arrow-undo-outline" : "archive-outline"}
              size={20}
              color={theme.text}
            />
            <Text style={s.label}>
              {archived ? t("chat.unarchive") : t("chat.archive")}
            </Text>
          </Pressable>
          <View style={s.divider} />
        </>
      ) : null}
      <Pressable style={s.item} onPress={onDelete}>
        <Ionicons name="trash-outline" size={20} color={theme.danger} />
        <Text style={[s.label, s.labelDanger]}>{t("common.delete")}</Text>
      </Pressable>
    </>
  );

  if (placement === "menu") {
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
        <View
          style={[
            s.menuPanel,
            { top: insets.top + CHAT_HEADER_BAR_HEIGHT + 4, right: 10 },
          ]}
        >
          {title ? (
            <Text style={s.menuTitle} numberOfLines={1}>
              {title}
            </Text>
          ) : null}
          {actionRows}
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
      backgroundColor: "transparent",
    },
    menuPanel: {
      position: "absolute",
      minWidth: 220,
      maxWidth: 280,
      borderRadius: 14,
      backgroundColor: C.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
      overflow: "hidden",
      shadowColor: "#000",
      shadowOpacity: 0.18,
      shadowRadius: 16,
      shadowOffset: { width: 0, height: 8 },
      elevation: 12,
    },
    menuTitle: {
      fontSize: 12,
      fontWeight: "600",
      color: C.textSecondary,
      paddingHorizontal: 16,
      paddingTop: 12,
      paddingBottom: 4,
    },
    item: {
      flexDirection: "row",
      alignItems: "center",
      paddingHorizontal: 18,
      paddingVertical: 14,
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

import { useMemo, type ComponentProps } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { ChatOverflowMenu } from "@/components/chat/ChatOverflowMenu";
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
   * `sheet` — bottom action sheet.
   * `menu` — shared floating overflow card (chat ⋮ + drawer long-press).
   */
  placement?: "sheet" | "menu";
  /** Top chrome height under the status bar when `placement="menu"`. */
  headerBarHeight?: number;
};

type IonName = ComponentProps<typeof Ionicons>["name"];

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
  headerBarHeight,
}: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeSheetStyles(theme), [theme]);

  if (placement === "menu") {
    return (
      <ChatOverflowMenu
        visible={visible}
        title={title}
        pinned={pinned}
        archived={archived}
        headerBarHeight={headerBarHeight}
        onClose={onClose}
        onShare={onShare}
        onRename={onRename}
        onTogglePin={onTogglePin}
        onToggleArchive={onToggleArchive}
        onDelete={onDelete}
      />
    );
  }

  const sheetRow = (
    icon: IonName,
    label: string,
    onPress: () => void,
    danger = false,
  ) => (
    <Pressable style={s.item} onPress={onPress}>
      <Ionicons
        name={icon}
        size={20}
        color={danger ? theme.danger : theme.text}
      />
      <Text style={[s.label, danger && s.labelDanger]}>{label}</Text>
    </Pressable>
  );

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
      <View style={s.group}>
        {sheetRow("share-social-outline", t("chat.share"), onShare)}
        <View style={s.divider} />
        {sheetRow("pencil-outline", t("chat.rename"), onRename)}
        <View style={s.divider} />
        {sheetRow(
          pinned ? "pin" : "pin-outline",
          pinned ? t("chat.unpin") : t("chat.pin"),
          onTogglePin,
        )}
        <View style={s.divider} />
        {onToggleArchive ? (
          <>
            {sheetRow(
              archived ? "arrow-undo-outline" : "archive-outline",
              archived ? t("chat.unarchive") : t("chat.archive"),
              onToggleArchive,
            )}
            <View style={s.divider} />
          </>
        ) : null}
        {sheetRow("trash-outline", t("common.delete"), onDelete, true)}
      </View>
      <Pressable style={s.cancelBtn} onPress={onClose}>
        <Text style={s.cancelText}>{t("common.cancel")}</Text>
      </Pressable>
    </AppSheet>
  );
}

function makeSheetStyles(C: Theme) {
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
    item: {
      flexDirection: "row",
      alignItems: "center",
      paddingHorizontal: 20,
      paddingVertical: 14,
      gap: 16,
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

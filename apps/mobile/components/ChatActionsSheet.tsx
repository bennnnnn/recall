import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
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
}: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);

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
      </View>
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
    item: {
      flexDirection: "row",
      alignItems: "center",
      paddingHorizontal: 18,
      paddingVertical: 16,
      gap: 14,
    },
    label: { fontSize: 17, color: C.text, fontWeight: "400", flex: 1 },
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

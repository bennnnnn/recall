import { useEffect, useMemo } from "react";
import { Keyboard, StyleSheet, Text } from "react-native";
import type { ComponentProps } from "react";
import { useTranslation } from "react-i18next";

import { ActionSheetRow, makeActionSheetPanelStyle } from "@/components/ActionSheetRow";
import { AppSheet } from "@/components/AppSheet";
import { Theme, useTheme } from "@/lib/theme";

type IconName = ComponentProps<typeof ActionSheetRow>["icon"];

type Props = {
  visible: boolean;
  title: string | null;
  pinned: boolean;
  archived?: boolean;
  onClose: () => void;
  onShare: () => void;
  /** Chat ⋮ menu only — export the thread as PDF. */
  onExportPdf?: () => void;
  onRename: () => void;
  onTogglePin: () => void;
  onToggleArchive?: () => void;
  onDelete: () => void;
  /** Drawer only — enter multi-select with this chat checked. */
  onSelectChats?: () => void;
};

type Action = {
  key: string;
  icon: IconName;
  label: string;
  onPress: () => void;
  danger?: boolean;
};

export function ChatActionsSheet({
  visible,
  title,
  pinned,
  archived = false,
  onClose,
  onShare,
  onExportPdf,
  onRename,
  onTogglePin,
  onToggleArchive,
  onDelete,
  onSelectChats,
}: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const panelStyle = useMemo(() => makeActionSheetPanelStyle(theme), [theme]);

  useEffect(() => {
    if (visible) Keyboard.dismiss();
  }, [visible]);

  const actions = useMemo(() => {
    const rows: Action[] = [
      { key: "share", icon: "share-outline", label: t("chat.share"), onPress: onShare },
    ];
    if (onExportPdf) {
      rows.push({
        key: "export-pdf",
        icon: "document-text-outline",
        label: t("chat.export_pdf"),
        onPress: onExportPdf,
      });
    }
    rows.push({ key: "rename", icon: "create-outline", label: t("chat.rename"), onPress: onRename });
    if (!archived) {
      rows.push({ key: "pin", icon: "pin-outline", label: pinned ? t("chat.unpin") : t("chat.pin"), onPress: onTogglePin });
    }
    if (onToggleArchive) {
      rows.push({
        key: "archive",
        icon: archived ? "arrow-undo-outline" : "archive-outline",
        label: archived ? t("chat.unarchive") : t("chat.archive"),
        onPress: onToggleArchive,
      });
    }
    if (onSelectChats) {
      rows.push({
        key: "select",
        icon: "checkbox-outline",
        label: t("drawer.select"),
        onPress: onSelectChats,
      });
    }
    rows.push({
      key: "delete",
      icon: "trash-outline",
      label: t("common.delete"),
      onPress: onDelete,
      danger: true,
    });
    return rows;
  }, [
    archived,
    onDelete,
    onExportPdf,
    onRename,
    onSelectChats,
    onShare,
    onToggleArchive,
    onTogglePin,
    pinned,
    t,
  ]);

  return (
    <AppSheet
      visible={visible}
      onClose={onClose}
      variant="bottom"
      withHandle
      floating
      keyboardAvoiding
      minBottomPadding={12}
      contentContainerStyle={panelStyle}
    >
      {title ? (
        <Text style={s.title} numberOfLines={2}>
          {title}
        </Text>
      ) : null}
      {actions.map((action) => (
        <ActionSheetRow
          key={action.key}
          icon={action.icon}
          label={action.label}
          onPress={action.onPress}
          theme={theme}
          danger={action.danger}
        />
      ))}
    </AppSheet>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    title: {
      fontSize: 13,
      fontWeight: "600",
      color: C.textSecondary,
      textAlign: "center",
      paddingHorizontal: 16,
      paddingTop: 4,
      paddingBottom: 4,
    },
  });
}

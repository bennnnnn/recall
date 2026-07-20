import { useMemo } from "react";
import { StyleSheet, Text } from "react-native";
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
  onRename: () => void;
  onTogglePin: () => void;
  onToggleArchive?: () => void;
  onDelete: () => void;
  /** Open Settings → Models (chat ⋮ menu). */
  onOpenModels?: () => void;
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
  onRename,
  onTogglePin,
  onToggleArchive,
  onDelete,
  onOpenModels,
  onSelectChats,
}: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const panelStyle = useMemo(() => makeActionSheetPanelStyle(theme), [theme]);

  const actions = useMemo(() => {
    const rows: Action[] = [
      { key: "share", icon: "share-outline", label: t("chat.share"), onPress: onShare },
      { key: "rename", icon: "pencil-outline", label: t("chat.rename"), onPress: onRename },
      {
        key: "pin",
        icon: pinned ? "pin" : "pin-outline",
        label: pinned ? t("chat.unpin") : t("chat.pin"),
        onPress: onTogglePin,
      },
    ];
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
    if (onOpenModels) {
      // options-outline matches outline weight better than hardware-chip.
      rows.push({
        key: "models",
        icon: "options-outline",
        label: t("settings.model"),
        onPress: onOpenModels,
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
    onOpenModels,
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
      minBottomPadding={12}
      contentContainerStyle={panelStyle}
    >
      {title ? (
        <Text style={s.title} numberOfLines={2}>
          {title}
        </Text>
      ) : null}
      {actions.map((action, index) => (
        <ActionSheetRow
          key={action.key}
          icon={action.icon}
          label={action.label}
          onPress={action.onPress}
          theme={theme}
          showDivider={index > 0}
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

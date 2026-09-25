import { useEffect, useMemo } from "react";
import { Keyboard, StyleSheet, Text, type ImageSourcePropType } from "react-native";
import type { ComponentProps } from "react";
import { useTranslation } from "react-i18next";

import { ActionSheetRow, makeActionSheetPanelStyle } from "@/components/ActionSheetRow";
import { Sheet } from "@/ui/overlay/Sheet";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import { Space } from "@/lib/space";

type IconName = ComponentProps<typeof ActionSheetRow>["icon"];

const menuIcons = {
  share: require("@/assets/menu-icons/share.png") as ImageSourcePropType,
  rename: require("@/assets/menu-icons/rename.png") as ImageSourcePropType,
  pin: require("@/assets/menu-icons/pin.png") as ImageSourcePropType,
  archive: require("@/assets/menu-icons/archive.png") as ImageSourcePropType,
  pdf: require("@/assets/menu-icons/pdf.png") as ImageSourcePropType,
  pdfDark: require("@/assets/menu-icons/pdf-dark.png") as ImageSourcePropType,
};

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
  image?: ImageSourcePropType;
  preserveImageColor?: boolean;
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
      {
        key: "share",
        icon: "share-outline",
        image: menuIcons.share,
        label: t("chat.share"),
        onPress: onShare,
      },
    ];
    if (onExportPdf) {
      rows.push({
        key: "export-pdf",
        icon: "document-text-outline",
        image: theme.isDark ? menuIcons.pdfDark : menuIcons.pdf,
        preserveImageColor: true,
        label: t("chat.export_pdf"),
        onPress: onExportPdf,
      });
    }
    rows.push({
      key: "rename",
      icon: "create-outline",
      image: menuIcons.rename,
      label: t("chat.rename"),
      onPress: onRename,
    });
    if (!archived) {
      rows.push({
        key: "pin",
        icon: "pin-outline",
        image: menuIcons.pin,
        label: pinned ? t("chat.unpin") : t("chat.pin"),
        onPress: onTogglePin,
      });
    }
    if (onToggleArchive) {
      rows.push({
        key: "archive",
        icon: archived ? "arrow-undo-outline" : "archive-outline",
        image: archived ? undefined : menuIcons.archive,
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
    theme.isDark,
  ]);

  return (
    <Sheet
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
          image={action.image}
          preserveImageColor={action.preserveImageColor}
          label={action.label}
          onPress={action.onPress}
          theme={theme}
          danger={action.danger}
        />
      ))}
    </Sheet>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    title: {
      ...Type.compact,
      fontWeight: "600",
      color: C.textSecondary,
      textAlign: "center",
      paddingHorizontal: Space.md,
      paddingTop: Space.xxs,
      paddingBottom: Space.xxs,
    },
  });
}

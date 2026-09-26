import { useTranslation } from "react-i18next";

import { Menu, type MenuEntry } from "@/ui/overlay/Menu";

type Props = {
  visible: boolean;
  canOpenChat: boolean;
  /** Where the tile was long-pressed. */
  anchorPoint: { x: number; y: number } | null;
  onClose: () => void;
  onUseInChat: () => void;
  onOpenChat: () => void;
  onShare: () => void;
  onDelete: () => void;
};

/** Library long-press: use, open, share, or delete one photo or file. */
export function GalleryItemActionsMenu({
  visible,
  canOpenChat,
  anchorPoint,
  onClose,
  onUseInChat,
  onOpenChat,
  onShare,
  onDelete,
}: Props) {
  const { t } = useTranslation();
  const items: MenuEntry[] = [
    { key: "use", icon: "attach", label: t("gallery.use_in_chat"), onPress: onUseInChat },
  ];
  if (canOpenChat) {
    items.push({ key: "open", icon: "message", label: t("gallery.open_chat"), onPress: onOpenChat });
  }
  items.push(
    { key: "share", icon: "share", label: t("gallery.share"), onPress: onShare },
    { key: "delete", icon: "trash", label: t("common.delete"), onPress: onDelete, destructive: true },
  );

  return (
    <Menu
      visible={visible}
      onClose={onClose}
      anchorPoint={anchorPoint}
      items={items}
      testID="gallery-item-menu"
    />
  );
}

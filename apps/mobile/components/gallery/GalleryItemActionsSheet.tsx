import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { ActionSheetRow, makeActionSheetPanelStyle } from "@/components/ActionSheetRow";
import { AppSheet } from "@/components/AppSheet";
import { useTheme } from "@/lib/theme";

type Props = {
  visible: boolean;
  canOpenChat: boolean;
  onClose: () => void;
  onOpenChat: () => void;
  onShare: () => void;
  onDelete: () => void;
};

export function GalleryItemActionsSheet({
  visible,
  canOpenChat,
  onClose,
  onOpenChat,
  onShare,
  onDelete,
}: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const panelStyle = useMemo(() => makeActionSheetPanelStyle(theme), [theme]);

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
      {canOpenChat ? (
        <ActionSheetRow
          icon="chatbubble-outline"
          label={t("gallery.open_chat")}
          onPress={onOpenChat}
          theme={theme}
        />
      ) : null}
      <ActionSheetRow
        icon="share-outline"
        label={t("gallery.share")}
        onPress={onShare}
        theme={theme}
      />
      <ActionSheetRow
        icon="trash-outline"
        label={t("common.delete")}
        onPress={onDelete}
        theme={theme}
        danger
      />
    </AppSheet>
  );
}

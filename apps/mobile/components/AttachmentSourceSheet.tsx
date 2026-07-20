import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { ActionSheetRow, makeActionSheetPanelStyle } from "@/components/ActionSheetRow";
import { AppSheet } from "@/components/AppSheet";
import { selection } from "@/lib/haptics";
import { useTheme } from "@/lib/theme";

export type AttachmentSource = "camera" | "photo" | "file" | "solve_math_camera";

type Props = {
  visible: boolean;
  onClose: () => void;
  onSelect: (source: AttachmentSource) => void;
};

/** Attach / math-scan source picker — same floating AppSheet chrome as chat actions. */
export function AttachmentSourceSheet({ visible, onClose, onSelect }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const panelStyle = useMemo(() => makeActionSheetPanelStyle(theme), [theme]);

  const pick = (source: AttachmentSource) => {
    selection();
    onSelect(source);
  };

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
      <ActionSheetRow
        icon="scan-outline"
        label={t("chat.attach_solve_math_camera")}
        onPress={() => pick("solve_math_camera")}
        theme={theme}
      />
      <ActionSheetRow
        icon="camera-outline"
        label={t("chat.attach_camera")}
        onPress={() => pick("camera")}
        theme={theme}
        showDivider
      />
      <ActionSheetRow
        icon="images-outline"
        label={t("chat.attach_photo")}
        onPress={() => pick("photo")}
        theme={theme}
        showDivider
      />
      <ActionSheetRow
        icon="document-outline"
        label={t("chat.attach_file")}
        onPress={() => pick("file")}
        theme={theme}
        showDivider
      />
    </AppSheet>
  );
}

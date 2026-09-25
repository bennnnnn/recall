import { useEffect, useMemo } from "react";
import { Keyboard, StyleSheet, Text } from "react-native";
import { useTranslation } from "react-i18next";

import { ActionSheetRow, makeActionSheetPanelStyle } from "@/components/ActionSheetRow";
import { Sheet } from "@/ui/overlay/Sheet";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Space } from "@/lib/space";

type Props = {
  visible: boolean;
  paused: boolean;
  busy: boolean;
  onClose: () => void;
  onEdit: () => void;
  onTogglePause: () => void;
  onShare: () => void;
  onDelete: () => void;
};

/** My Job dashboard ⋯ menu: edit / pause-resume / share / delete the search. */
export function JobSearchActionsSheet({
  visible,
  paused,
  busy,
  onClose,
  onEdit,
  onTogglePause,
  onShare,
  onDelete,
}: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const panelStyle = useMemo(() => makeActionSheetPanelStyle(theme), [theme]);

  useEffect(() => {
    if (visible) Keyboard.dismiss();
  }, [visible]);

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
      <Text style={s.title}>{t("my_job.title")}</Text>
      <ActionSheetRow
        icon="pencil"
        label={t("my_job.edit")}
        onPress={onEdit}
        theme={theme}
      />
      <ActionSheetRow
        icon={paused ? "play" : "pause"}
        label={paused ? t("my_job.resume") : t("my_job.pause")}
        onPress={() => {
          if (busy) return;
          onTogglePause();
        }}
        theme={theme}
      />
      <ActionSheetRow
        icon="share"
        label={t("my_job.share")}
        onPress={onShare}
        theme={theme}
      />
      <ActionSheetRow
        icon="trash"
        label={t("common.delete")}
        onPress={() => {
          if (busy) return;
          onDelete();
        }}
        theme={theme}
        danger
      />
    </Sheet>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    title: {
      ...Type.compact,
      ...Weight.semibold,
      color: C.textSecondary,
      textAlign: "center",
      paddingHorizontal: Space.md,
      paddingTop: Space.xxs,
      paddingBottom: Space.xxs,
    },
  });
}

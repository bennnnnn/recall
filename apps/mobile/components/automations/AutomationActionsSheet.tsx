import { useMemo } from "react";
import type { ComponentProps } from "react";
import { useTranslation } from "react-i18next";

import { ActionSheetRow, makeActionSheetPanelStyle } from "@/components/ActionSheetRow";
import { AppSheet } from "@/components/AppSheet";
import type { AutomationStatus } from "@/lib/api";
import { useTheme } from "@/lib/theme";

type IconName = ComponentProps<typeof ActionSheetRow>["icon"];

type Action = {
  key: string;
  icon: IconName;
  label: string;
  onPress: () => void;
  danger?: boolean;
};

export function AutomationActionsSheet({
  visible,
  status,
  chatId,
  onClose,
  onEdit,
  onShare,
  onTogglePause,
  onRunHistory,
  onDelete,
  hideTogglePause = false,
}: {
  visible: boolean;
  status: AutomationStatus;
  chatId?: string;
  onClose: () => void;
  onEdit: () => void;
  onShare: () => void;
  onTogglePause: () => void;
  onRunHistory?: () => void;
  onDelete: () => void;
  /** The detail screen already has a header pause/resume icon — omit the
   * duplicate row there. The list's long-press sheet keeps it (no header). */
  hideTogglePause?: boolean;
}) {
  const theme = useTheme();
  const { t } = useTranslation();
  const panelStyle = useMemo(() => makeActionSheetPanelStyle(theme), [theme]);

  const actions = useMemo<Action[]>(() => {
    const rows: Action[] = [
      { key: "edit", icon: "create-outline", label: t("automations.edit"), onPress: onEdit },
      { key: "share", icon: "share-outline", label: t("automations.share"), onPress: onShare },
    ];
    if (status !== "completed" && !hideTogglePause) {
      rows.push({
        key: "toggle-pause",
        icon: status === "paused" ? "play-outline" : "pause-outline",
        label: t(status === "paused" ? "automations.resume" : "automations.pause"),
        onPress: onTogglePause,
      });
    }
    if (onRunHistory && chatId) {
      rows.push({
        key: "run-history",
        icon: "time-outline",
        label: t("automations.see_run_history"),
        onPress: onRunHistory,
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
  }, [status, chatId, hideTogglePause, onEdit, onShare, onTogglePause, onRunHistory, onDelete, t]);

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

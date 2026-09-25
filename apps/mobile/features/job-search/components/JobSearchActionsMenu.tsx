import { useEffect, type RefObject } from "react";
import { Keyboard, type View } from "react-native";
import { useTranslation } from "react-i18next";

import { Menu } from "@/ui/overlay/Menu";

type Props = {
  visible: boolean;
  paused: boolean;
  busy: boolean;
  /** The search card's ⋮ button. */
  anchorRef: RefObject<View | null>;
  onClose: () => void;
  onEdit: () => void;
  onTogglePause: () => void;
  onShare: () => void;
  onDelete: () => void;
};

/** My Job ⋮: edit, pause or resume, share, and delete the search. */
export function JobSearchActionsMenu({
  visible,
  paused,
  busy,
  anchorRef,
  onClose,
  onEdit,
  onTogglePause,
  onShare,
  onDelete,
}: Props) {
  const { t } = useTranslation();

  useEffect(() => {
    if (visible) Keyboard.dismiss();
  }, [visible]);

  return (
    <Menu
      visible={visible}
      onClose={onClose}
      anchorRef={anchorRef}
      title={t("my_job.title")}
      testID="job-search-actions-menu"
      items={[
        { key: "edit", icon: "pencil", label: t("my_job.edit"), onPress: onEdit },
        {
          key: "pause",
          icon: paused ? "play" : "pause",
          label: paused ? t("my_job.resume") : t("my_job.pause"),
          onPress: onTogglePause,
          disabled: busy,
        },
        { key: "share", icon: "share", label: t("my_job.share"), onPress: onShare },
        {
          key: "delete",
          icon: "trash",
          label: t("common.delete"),
          onPress: onDelete,
          destructive: true,
          disabled: busy,
        },
      ]}
    />
  );
}

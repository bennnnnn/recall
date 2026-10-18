import { useEffect } from "react";
import { useNavigation, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { plainHeaderItems, StackBackButton } from "@/ui/controls/StackBackButton";
import { StateView } from "@/ui/feedback/StateView";
import {
  SettingsGroup,
  SettingsLinkRow,
  SettingsPage,
  useSettingsAction,
} from "@/features/account/components/settingsUi";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useAuth } from "@/contexts/AuthContext";
import { useDataControls } from "@/features/account/hooks/useDataControls";
import { api } from "@/lib/api";
import { invalidateChatListCache } from "@/lib/cache/chatListCache";
import { notifyDestructive } from "@/lib/haptics";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { confirmDialog } from "@/ui/overlay/dialogs";

export default function DataControlsScreen() {
  const { token } = useAuth();
  const { progress, exportData, deleteAccount } = useDataControls();
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const router = useRouter();
  const navigation = useNavigation();
  const action = useSettingsAction();
  const busy = progress !== "idle";

  useEffect(() => {
    const back = busy ? null : <StackBackButton fallback="/settings" />;
    navigation.setOptions({
      gestureEnabled: !busy,
      headerLeft: () => back,
      unstable_headerLeftItems: () => plainHeaderItems(back),
    });
  }, [busy, navigation]);

  const doExport = async () => {
    if (!token || busy) return;
    try {
      await exportData();
    } catch (error) {
      const message = error instanceof Error ? error.message : "";
      if (!message.toLowerCase().includes("cancel")) {
        reportRecoverableError(feedback, t("settings.export_failed"));
      }
    }
  };

  const confirmDeleteAccount = () => {
    if (!token || busy) return;
    void confirmDialog({
      title: t("delete.title"),
      message: t("delete.message"),
      cancelLabel: t("common.cancel"),
      confirmLabel: t("common.delete"),
      destructive: true,
    }).then(async (ok) => {
      if (!ok) return;
      if (await deleteAccount()) {
        notifyDestructive();
        router.replace("/login");
      } else {
        reportRecoverableError(feedback, t("settings.delete_failed"));
      }
    });
  };

  const archiveAll = () =>
    void action.run(
      "archive",
      async () => {
        if (!token) return;
        await api.archiveAllChats(token);
        invalidateChatListCache();
      },
      {
        confirm: {
          title: t("settings.archive_all_chats"),
          message: t("settings.archive_all_confirm"),
          cancelLabel: t("common.cancel"),
          confirmLabel: t("settings.archive_all_chats"),
        },
      },
    );

  const deleteAll = () =>
    void action.run(
      "delete",
      async () => {
        if (!token) return;
        await api.deleteAllChats(token);
        notifyDestructive();
        invalidateChatListCache();
      },
      {
        confirm: {
          title: t("settings.delete_all_chats_title"),
          message: t("settings.delete_all_chats_body"),
          cancelLabel: t("common.cancel"),
          confirmLabel: t("settings.delete_all_chats"),
          destructive: true,
        },
      },
    );

  // Deleting signs out mid-way; keep the progress up instead of redirecting.
  if (progress === "deleting") {
    return (
      <StateView
        variant="loading"
        title={t("settings.delete_progress")}
        message={t("settings.delete_progress_body")}
      />
    );
  }

  if (progress === "exporting") {
    return (
      <StateView
        variant="loading"
        title={t("settings.export_progress")}
        message={t("settings.export_progress_body")}
      />
    );
  }

  return (
    <SettingsPage>
      <SettingsGroup label={t("settings.chats_group")}>
        <SettingsLinkRow
          title={t("settings.archived_chats")}
          href="/settings/archived-chats"
        />
        <SettingsLinkRow
          title={t("settings.archive_all_chats")}
          busy={action.busy === "archive"}
          disabled={action.busy !== null}
          onPress={archiveAll}
        />
        <SettingsLinkRow
          title={t("settings.delete_all_chats")}
          danger
          busy={action.busy === "delete"}
          disabled={action.busy !== null}
          onPress={deleteAll}
        />
      </SettingsGroup>
      <SettingsGroup label={t("settings.your_data")}>
        <SettingsLinkRow title={t("settings.export")} onPress={() => void doExport()} />
      </SettingsGroup>
      <SettingsGroup label={t("settings.account")}>
        <SettingsLinkRow
          title={t("settings.delete")}
          danger
          onPress={confirmDeleteAccount}
        />
      </SettingsGroup>
    </SettingsPage>
  );
}

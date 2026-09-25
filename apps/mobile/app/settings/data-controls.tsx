import { useEffect, useMemo, useState } from "react";
import { Alert, ScrollView, View } from "react-native";
import { Redirect, useNavigation, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { StackBackButton } from "@/ui/controls/StackBackButton";
import { StateView } from "@/ui/feedback/StateView";
import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsLinkRow,
} from "@/components/settings/settingsUi";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useAuth } from "@/contexts/AuthContext";
import { useDataControls } from "@/hooks/useDataControls";
import { api } from "@/lib/api";
import { invalidateChatListCache } from "@/lib/cache/chatListCache";
import { notifyDestructive } from "@/lib/haptics";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";
import { reportRecoverableError } from "@/lib/reportRecoverableError";

export default function DataControlsScreen() {
  const { token } = useAuth();
  const { progress, exportData, deleteAccount } = useDataControls();
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const navigation = useNavigation();
  const busy = progress !== "idle";
  const [bulkBusy, setBulkBusy] = useState<"archive" | "delete" | null>(null);

  useEffect(() => {
    navigation.setOptions({
      gestureEnabled: !busy,
      headerLeft: busy
        ? () => null
        : () => <StackBackButton fallback="/settings" />,
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
    Alert.alert(t("delete.title"), t("delete.message"), [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("common.delete"),
        style: "destructive",
        onPress: () => {
          void runDelete();
        },
      },
    ]);
  };

  const runDelete = async () => {
    const deleted = await deleteAccount();
    if (deleted) {
      notifyDestructive();
      router.replace("/login");
    } else {
      reportRecoverableError(feedback, t("settings.delete_failed"));
    }
  };

  const confirmArchiveAll = () => {
    if (!token || bulkBusy) return;
    Alert.alert(t("settings.archive_all_chats"), t("settings.archive_all_confirm"), [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("settings.archive_all_chats"),
        onPress: () => {
          void (async () => {
            if (!token) return;
            setBulkBusy("archive");
            try {
              await api.archiveAllChats(token);
              invalidateChatListCache();
            } catch {
              reportRecoverableError(feedback, t("common.error"));
            } finally {
              setBulkBusy(null);
            }
          })();
        },
      },
    ]);
  };

  const confirmDeleteAll = () => {
    if (!token || bulkBusy) return;
    Alert.alert(t("settings.delete_all_chats_title"), t("settings.delete_all_chats_body"), [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("settings.delete_all_chats"),
        style: "destructive",
        onPress: () => {
          void (async () => {
            if (!token) return;
            setBulkBusy("delete");
            try {
              await api.deleteAllChats(token);
              notifyDestructive();
              invalidateChatListCache();
            } catch {
              reportRecoverableError(feedback, t("common.error"));
            } finally {
              setBulkBusy(null);
            }
          })();
        },
      },
    ]);
  };

  if (!token && progress !== "deleting") return <Redirect href="/login" />;

  if (progress === "exporting") {
    return (
      <StateView
        variant="loading"
        title={t("settings.export_progress")}
        message={t("settings.export_progress_body")}
      />
    );
  }

  if (progress === "deleting") {
    return (
      <StateView
        variant="loading"
        title={t("settings.delete_progress")}
        message={t("settings.delete_progress_body")}
      />
    );
  }

  return (
    <ScrollView
      style={s.scroll}
      contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
    >
      <SettingsGroup label={t("settings.chats_group")} styles={s}>
        <SettingsLinkRow
          title={t("settings.archived_chats")}
          onPress={() => router.push("/settings/archived-chats")}
          styles={s}
          theme={theme}
        />
        <View style={s.menuSeparator} />
        <SettingsLinkRow
          title={t("settings.archive_all_chats")}
          onPress={confirmArchiveAll}
          styles={s}
          theme={theme}
        />
        <View style={s.menuSeparator} />
        <SettingsLinkRow
          title={t("settings.delete_all_chats")}
          danger
          onPress={confirmDeleteAll}
          styles={s}
          theme={theme}
        />
      </SettingsGroup>
      <SettingsGroup styles={s}>
        <SettingsLinkRow
          title={t("settings.export")}
          onPress={() => void doExport()}
          styles={s}
          theme={theme}
        />
      </SettingsGroup>
      <SettingsGroup styles={s}>
        <SettingsLinkRow
          title={t("settings.delete")}
          danger
          onPress={confirmDeleteAccount}
          styles={s}
          theme={theme}
        />
      </SettingsGroup>
    </ScrollView>
  );
}

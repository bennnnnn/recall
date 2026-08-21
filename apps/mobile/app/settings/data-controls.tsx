import { useEffect, useMemo } from "react";
import { Alert, ScrollView } from "react-native";
import { Redirect, useNavigation, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { StackBackButton } from "@/components/StackBackButton";
import { StateView } from "@/components/StateView";
import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsLinkRow,
} from "@/components/settings/settingsUi";
import { useDataControls } from "@/hooks/useDataControls";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

export default function DataControlsScreen() {
  const { token, progress, exportData, deleteAccount } = useDataControls();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const navigation = useNavigation();
  const busy = progress !== "idle";

  useEffect(() => {
    navigation.setOptions({
      gestureEnabled: !busy,
      headerLeft: busy
        ? () => null
        : () => <StackBackButton fallback="/settings" />,
    });
  }, [busy, navigation]);

  if (!token && progress !== "deleting") return <Redirect href="/login" />;

  const doExport = async () => {
    if (!token || busy) return;
    try {
      await exportData();
    } catch (error) {
      const message = error instanceof Error ? error.message : "";
      if (!message.toLowerCase().includes("cancel")) {
        Alert.alert(t("common.error"), t("settings.export_failed"));
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
      router.replace("/login");
    } else {
      Alert.alert(t("common.error"), t("settings.delete_failed"));
    }
  };

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
      <SettingsGroup styles={s}>
        <SettingsLinkRow
          icon="download-outline"
          title={t("settings.export")}
          subtitle={t("settings.export_desc")}
          onPress={() => void doExport()}
          styles={s}
          theme={theme}
        />
      </SettingsGroup>
      <SettingsGroup styles={s}>
        <SettingsLinkRow
          icon="trash-outline"
          title={t("settings.delete")}
          subtitle={t("settings.delete_desc")}
          danger
          onPress={confirmDeleteAccount}
          styles={s}
          theme={theme}
        />
      </SettingsGroup>
    </ScrollView>
  );
}

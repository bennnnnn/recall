import { useMemo } from "react";
import { Alert, ScrollView, Share, View } from "react-native";
import { Redirect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { makeSettingsStyles, NavRow } from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { useTheme } from "@/lib/theme";

export default function DataControlsScreen() {
  const { token, signOut } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const router = useRouter();

  if (!token) return <Redirect href="/login" />;

  const doExport = async () => {
    try {
      const data = await api.exportData(token);
      const payload = JSON.stringify(data, null, 2);
      // The OS share sheet has platform-dependent size limits and silently
      // truncates or fails on very large messages. For a long-running account
      // the full export can be several MB, so warn before sharing and let the
      // user decide rather than discovering a silent truncation later.
      const MAX_SHARE_BYTES = 2_000_000;
      if (payload.length > MAX_SHARE_BYTES) {
        Alert.alert(
          t("settings.export_large_title"),
          t("settings.export_large_message", { size_mb: Math.round(payload.length / 1_000_000) }),
          [
            { text: t("common.cancel"), style: "cancel" },
            { text: t("common.continue"), onPress: () => Share.share({ message: payload }) },
          ],
        );
        return;
      }
      await Share.share({ message: payload });
    } catch (error) {
      const message = error instanceof Error ? error.message : "";
      if (!message.toLowerCase().includes("cancel")) {
        Alert.alert(t("common.error"), t("settings.export_failed"));
      }
    }
  };

  const confirmDeleteAccount = () => {
    Alert.alert(t("delete.title"), t("delete.message"), [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("common.delete"),
        style: "destructive",
        onPress: async () => {
          try {
            await api.deleteAccount(token);
            await signOut();
            router.replace("/login");
          } catch {
            Alert.alert(t("common.error"), t("settings.delete_failed"));
          }
        },
      },
    ]);
  };

  return (
    <ScrollView
      style={s.scroll}
      contentContainerStyle={[s.content, { paddingBottom: insets.bottom + 24 }]}
    >
      <View style={s.menuStack}>
        <View style={s.footerGroup}>
          <NavRow
            icon="download-outline"
            title={t("settings.export")}
            onPress={doExport}
            compact
            styles={s}
            theme={theme}
          />
        </View>
        <View style={s.footerGroup}>
          <NavRow
            icon="trash-outline"
            title={t("settings.delete")}
            onPress={confirmDeleteAccount}
            danger
            compact
            styles={s}
            theme={theme}
          />
        </View>
      </View>
    </ScrollView>
  );
}

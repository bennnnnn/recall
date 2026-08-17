import { useEffect, useMemo, useState } from "react";
import { Alert, ScrollView, View } from "react-native";
import { Redirect, useNavigation, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { StackBackButton } from "@/components/StackBackButton";
import { StateView } from "@/components/StateView";
import { makeSettingsStyles, NavRow } from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { isAccountDeleteComplete } from "@/lib/accountDelete";
import { api } from "@/lib/api";
import { formatExportJsonForShare, shareAccountExport } from "@/lib/exportData";
import { useTheme } from "@/lib/theme";

export default function DataControlsScreen() {
  const { token, signOut, setIgnoreUnauthorized } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const navigation = useNavigation();
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    navigation.setOptions({
      gestureEnabled: !deleting,
      headerLeft: deleting
        ? () => null
        : () => <StackBackButton fallback="/settings" />,
    });
  }, [deleting, navigation]);

  if (!token && !deleting) return <Redirect href="/login" />;

  const doExport = async () => {
    if (!token) return;
    try {
      const raw = await api.exportDataText(token);
      const payload = formatExportJsonForShare(raw);
      await shareAccountExport(payload);
    } catch (error) {
      const message = error instanceof Error ? error.message : "";
      if (!message.toLowerCase().includes("cancel")) {
        Alert.alert(t("common.error"), t("settings.export_failed"));
      }
    }
  };

  const confirmDeleteAccount = () => {
    if (!token || deleting) return;
    Alert.alert(t("delete.title"), t("delete.message"), [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("common.delete"),
        style: "destructive",
        onPress: () => {
          void runDelete(token);
        },
      },
    ]);
  };

  const runDelete = async (accessToken: string) => {
    setDeleting(true);
    setIgnoreUnauthorized(true);
    try {
      try {
        await api.deleteAccount(accessToken);
      } catch (error) {
        if (!isAccountDeleteComplete(error)) {
          throw error;
        }
      }
      await signOut();
      router.replace("/login");
    } catch {
      setIgnoreUnauthorized(false);
      setDeleting(false);
      Alert.alert(t("common.error"), t("settings.delete_failed"));
    }
  };

  if (deleting) {
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

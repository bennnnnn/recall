import { useCallback, useEffect, useMemo, useState } from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { StackBackButton } from "@/components/StackBackButton";
import { AccountSettingsSection } from "@/components/settings/AccountSettingsSection";
import { AppearanceSettingsRow } from "@/components/settings/AppearanceSettingsRow";
import { SettingsProfile } from "@/components/settings/SettingsProfile";
import {
  SettingsOverviewGroup,
  SettingsOverviewRow,
} from "@/components/settings/SettingsOverview";
import { useAuth } from "@/contexts/AuthContext";
import { useModels } from "@/hooks/useModels";
import { prefetchMemories } from "@/lib/cache/memoryListCache";
import {
  connectedCountFromStatus,
  fetchIntegrationStatus,
  getCachedConnectedCount,
} from "@/lib/cache/integrationStatusCache";
import { getNotificationPermissionGranted } from "@/lib/pushNotifications";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";

export default function SettingsScreen() {
  const { token, user, signOut } = useAuth();
  const { t } = useTranslation();
  const { isPro, autoEnabled, modelEnabledSet } = useModels();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const router = useRouter();

  const [connectedCount, setConnectedCount] = useState(getCachedConnectedCount);
  const [osPushGranted, setOsPushGranted] = useState<boolean | null>(null);

  const refreshSummary = useCallback(async () => {
    if (!token) return;
    const [integrationsR, pushGranted] = await Promise.allSettled([
      fetchIntegrationStatus(token),
      getNotificationPermissionGranted(),
    ]);
    if (integrationsR.status === "fulfilled" && integrationsR.value) {
      setConnectedCount(connectedCountFromStatus(integrationsR.value));
    }
    if (pushGranted.status === "fulfilled") {
      setOsPushGranted(pushGranted.value);
    }
  }, [token]);

  useFocusEffect(
    useCallback(() => {
      void refreshSummary();
    }, [refreshSummary]),
  );

  useEffect(() => {
    void getNotificationPermissionGranted()
      .then(setOsPushGranted)
      .catch(() => setOsPushGranted(false));
  }, []);

  if (!token) return <Redirect href="/login" />;

  const memoryValue = user?.memory_enabled ? t("settings.on") : t("settings.off");
  const modelsValue = autoEnabled
    ? t("settings.model_auto")
    : t("settings.models_enabled", { count: modelEnabledSet.size });
  const integrationsValue =
    connectedCount > 0
      ? t("settings.integrations_connected", { count: connectedCount })
      : t("settings.integration_not_connected");
  const notificationsOn =
    Boolean(user?.push_notifications_enabled) && osPushGranted === true;
  const notificationsValue =
    osPushGranted == null
      ? undefined
      : notificationsOn
        ? t("settings.on")
        : t("settings.off");

  return (
    <View style={s.root}>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={[
          s.content,
          { paddingTop: insets.top + Space.md, paddingBottom: insets.bottom + Space.xl },
        ]}
      >
        <View style={s.profileHeader}>
          <StackBackButton
            icon="arrow-back"
            style={s.backButton}
          />
          <SettingsProfile />
        </View>

        <SettingsOverviewGroup label={t("settings.experience")}>
          <AppearanceSettingsRow />
          <SettingsOverviewRow
            icon="person-circle-outline"
            title={t("settings.personalization")}
            accessibilityHint={t("settings.personalization_summary")}
            onPress={() => router.push("/settings/preferences")}
          />
          <SettingsOverviewRow
            icon="cube-outline"
            title={t("settings.memory")}
            accessibilityHint={t("settings.memory_desc")}
            value={memoryValue}
            onPress={() => {
              if (token) prefetchMemories(token);
              router.push("/settings/memory-settings");
            }}
          />
        </SettingsOverviewGroup>

        <AccountSettingsSection isPro={isPro} />

        <SettingsOverviewGroup label={t("settings.connections")}>
          <SettingsOverviewRow
            icon="notifications-outline"
            title={t("settings.notifications")}
            accessibilityHint={t("settings.notifications_summary")}
            value={notificationsValue}
            onPress={() => router.push("/settings/notifications")}
          />
          <SettingsOverviewRow
            icon="link-outline"
            title={t("settings.connected_apps")}
            accessibilityHint={t("settings.connected_apps_summary")}
            value={integrationsValue}
            onPress={() => router.push("/settings/integrations")}
          />
        </SettingsOverviewGroup>

        <SettingsOverviewGroup label={t("settings.advanced")}>
          <SettingsOverviewRow
            icon="sparkles-outline"
            title={t("settings.model")}
            accessibilityHint={t("settings.model_summary")}
            value={modelsValue}
            onPress={() => router.push("/settings/models")}
          />
        </SettingsOverviewGroup>

        <SettingsOverviewGroup label={t("settings.data_and_privacy")}>
          <SettingsOverviewRow
            icon="shield-outline"
            title={t("settings.data_controls")}
            accessibilityHint={t("settings.data_controls_summary")}
            onPress={() => router.push("/settings/data-controls")}
          />
          <SettingsOverviewRow
            icon="lock-closed-outline"
            title={t("settings.security")}
            accessibilityHint={t("settings.security_summary")}
            onPress={() => router.push("/settings/security")}
          />
        </SettingsOverviewGroup>

        <SettingsOverviewGroup label={t("settings.support")}>
          <SettingsOverviewRow
            icon="help-circle-outline"
            title={t("settings.help")}
            accessibilityHint={t("settings.help_summary")}
            onPress={() => router.push("/settings/help")}
          />
          <SettingsOverviewRow
            icon="information-circle-outline"
            title={t("settings.about")}
            accessibilityHint={t("settings.about_summary")}
            onPress={() => router.push("/settings/about")}
          />
        </SettingsOverviewGroup>

        <SettingsOverviewGroup>
          <SettingsOverviewRow
            icon="log-out-outline"
            title={t("settings.sign_out")}
            danger
            onPress={async () => {
              await signOut();
              router.replace("/login");
            }}
          />
        </SettingsOverviewGroup>
      </ScrollView>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: theme.bg },
    scroll: { flex: 1 },
    content: { paddingHorizontal: Space.gutter },
    profileHeader: {
      alignItems: "center",
      paddingBottom: Space.xs,
    },
    backButton: {
      position: "absolute",
      left: 0,
      marginLeft: 0,
      top: 0,
      width: 52,
      height: 52,
      borderRadius: 26,
      backgroundColor: theme.bg,
      shadowColor: theme.text,
      shadowOffset: { width: 0, height: Space.xs },
      shadowOpacity: 0.04,
      shadowRadius: Space.xl,
    },
  });
}

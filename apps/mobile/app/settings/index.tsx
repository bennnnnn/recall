import { useCallback, useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Avatar } from "@/components/Avatar";
import { AccountSettingsSection } from "@/components/settings/AccountSettingsSection";
import { AppearanceSettingsRow } from "@/components/settings/AppearanceSettingsRow";
import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsLinkRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useModels } from "@/hooks/useModels";
import { prefetchMemories } from "@/lib/cache/memoryListCache";
import {
  connectedCountFromStatus,
  fetchIntegrationStatus,
  getCachedConnectedCount,
} from "@/lib/cache/integrationStatusCache";
import { getDisplayName } from "@/lib/profile";
import { getNotificationPermissionGranted } from "@/lib/pushNotifications";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

export default function SettingsScreen() {
  const { token, user, signOut } = useAuth();
  const { t } = useTranslation();
  const { isPro, autoEnabled, modelEnabledSet } = useModels();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
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

  const planLabel = isPro ? t("settings.account_pro") : t("settings.account_free");
  const displayName = getDisplayName(user?.name, t("common.you"));
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
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
      >
        <View style={s.profileHeader}>
          <View style={s.profileAvatarWrap}>
            <Avatar name={user?.name ?? null} uri={user?.avatar_url} size={60} />
          </View>
          <View style={s.profileMeta}>
            <Text style={s.profileName} numberOfLines={1}>
              {displayName}
            </Text>
            {user?.email ? (
              <Text style={s.profileEmail} numberOfLines={1}>
                {user.email}
              </Text>
            ) : null}
            <View style={s.planPill}>
              <Text style={s.planPillText}>{planLabel}</Text>
            </View>
          </View>
        </View>

        <AccountSettingsSection styles={s} theme={theme} isPro={isPro} />

        <SettingsGroup label={t("settings.experience")} styles={s}>
          <AppearanceSettingsRow />
          <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
          <SettingsLinkRow
            icon="color-palette-outline"
            title={t("settings.personalization")}
            subtitle={t("settings.personalization_summary")}
            onPress={() => router.push("/settings/preferences")}
            styles={s}
            theme={theme}
          />
          <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
          <SettingsLinkRow
            icon="cube-outline"
            title={t("settings.memory")}
            subtitle={t("settings.memory_desc")}
            value={memoryValue}
            onPress={() => {
              if (token) prefetchMemories(token);
              router.push("/settings/memory-settings");
            }}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>

        <SettingsGroup label={t("settings.connections")} styles={s}>
          <SettingsLinkRow
            icon="notifications-outline"
            title={t("settings.notifications")}
            subtitle={t("settings.notifications_summary")}
            value={notificationsValue}
            onPress={() => router.push("/settings/notifications")}
            styles={s}
            theme={theme}
          />
          <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
          <SettingsLinkRow
            icon="link-outline"
            title={t("settings.connected_apps")}
            subtitle={t("settings.connected_apps_summary")}
            value={integrationsValue}
            onPress={() => router.push("/settings/integrations")}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>

        <SettingsGroup label={t("settings.advanced")} styles={s}>
          <SettingsLinkRow
            icon="sparkles-outline"
            title={t("settings.model")}
            subtitle={t("settings.model_summary")}
            value={modelsValue}
            onPress={() => router.push("/settings/models")}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>

        <SettingsGroup label={t("settings.data_and_privacy")} styles={s}>
          <SettingsLinkRow
            icon="shield-outline"
            title={t("settings.data_controls")}
            subtitle={t("settings.data_controls_summary")}
            onPress={() => router.push("/settings/data-controls")}
            styles={s}
            theme={theme}
          />
          <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
          <SettingsLinkRow
            icon="lock-closed-outline"
            title={t("settings.security")}
            subtitle={t("settings.security_summary")}
            onPress={() => router.push("/settings/security")}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>

        <SettingsGroup label={t("settings.support")} styles={s}>
          <SettingsLinkRow
            icon="help-circle-outline"
            title={t("settings.help")}
            subtitle={t("settings.help_summary")}
            onPress={() => router.push("/settings/help")}
            styles={s}
            theme={theme}
          />
          <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
          <SettingsLinkRow
            icon="information-circle-outline"
            title={t("settings.about")}
            subtitle={t("settings.about_summary")}
            onPress={() => router.push("/settings/about")}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>

        <View style={[s.footerGroup, s.signOut]}>
          <Pressable
            style={({ pressed }) => [s.signOutRow, pressed && s.rowPressed]}
            onPress={async () => {
              await signOut();
              router.replace("/login");
            }}
            accessibilityRole="button"
          >
            <Text style={s.signOutText}>{t("settings.sign_out")}</Text>
          </Pressable>
        </View>
      </ScrollView>
    </View>
  );
}

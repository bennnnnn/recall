import { useCallback, useMemo, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Avatar } from "@/components/Avatar";
import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsLinkRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useModels } from "@/hooks/useModels";
import { LANGUAGES } from "@/lib/i18n/languages";
import { prefetchMemories } from "@/lib/cache/memoryListCache";
import {
  connectedCountFromStatus,
  fetchIntegrationStatus,
  getCachedConnectedCount,
} from "@/lib/cache/integrationStatusCache";
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

  const refreshSummary = useCallback(async () => {
    if (!token) return;
    const integrationsR = await Promise.allSettled([fetchIntegrationStatus(token)]);
    if (integrationsR[0].status === "fulfilled" && integrationsR[0].value) {
      setConnectedCount(connectedCountFromStatus(integrationsR[0].value));
    }
  }, [token]);

  useFocusEffect(
    useCallback(() => {
      void refreshSummary();
    }, [refreshSummary]),
  );

  if (!token) return <Redirect href="/login" />;

  const planLabel = isPro ? t("settings.account_pro") : t("settings.account_free");
  const selectedLanguage =
    LANGUAGES.find((l) => l.code === (user?.locale ?? "en")) ?? LANGUAGES[0];
  const memoryValue = user?.memory_enabled ? t("settings.on") : t("settings.off");
  const modelsValue = autoEnabled
    ? t("settings.model_auto")
    : t("settings.models_enabled", { count: modelEnabledSet.size });
  const integrationsValue =
    connectedCount > 0
      ? t("settings.integrations_connected", { count: connectedCount })
      : t("settings.integration_not_connected");

  return (
    <View style={s.root}>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
      >
        <View style={s.profileHeader}>
          <View style={s.profileAvatarWrap}>
            <Avatar name={user?.name ?? null} uri={user?.avatar_url} size={80} />
          </View>
          {user?.email ? (
            <Text style={s.profileEmail} numberOfLines={1}>
              {user.email}
            </Text>
          ) : null}
          <View style={[s.planPill, isPro && s.planPillPro]}>
            <Text style={[s.planPillText, isPro && s.planPillTextPro]}>
              {planLabel}
            </Text>
          </View>
        </View>

        <SettingsGroup styles={s}>
          <SettingsLinkRow
            icon="person-outline"
            title={t("settings.profile")}
            onPress={() => router.push("/settings/profile")}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>

        <SettingsGroup label={t("settings.app")} styles={s}>
          <SettingsLinkRow
            icon="sparkles-outline"
            title={t("settings.model")}
            subtitle={t("settings.model_summary")}
            value={modelsValue}
            onPress={() => router.push("/settings/models")}
            styles={s}
            theme={theme}
          />
          <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
          <SettingsLinkRow
            icon="color-palette-outline"
            title={t("settings.personalization")}
            subtitle={t("settings.personalization_summary")}
            value={selectedLanguage.label}
            onPress={() => router.push("/settings/preferences")}
            styles={s}
            theme={theme}
          />
          <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
          <SettingsLinkRow
            icon="school-outline"
            title={t("settings.learning.title")}
            subtitle={t("settings.learning_summary")}
            onPress={() => router.push("/settings/learning")}
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
          <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
          <SettingsLinkRow
            icon="notifications-outline"
            title={t("settings.notifications")}
            subtitle={t("settings.notifications_summary")}
            value={user?.push_notifications_enabled ? t("settings.on") : t("settings.off")}
            onPress={() => router.push("/settings/notifications")}
            styles={s}
            theme={theme}
          />
          <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
          <SettingsLinkRow
            icon="link-outline"
            title={t("settings.integrations")}
            subtitle={t("settings.integrations_manage")}
            value={integrationsValue}
            onPress={() => router.push("/settings/integrations")}
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

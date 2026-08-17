import { useCallback, useMemo, useState } from "react";
import { Alert, Pressable, ScrollView, Text, View } from "react-native";
import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { AvatarUsageRing } from "@/components/AvatarUsageRing";
import { UpgradeSheet } from "@/components/UpgradeSheet";
import { SettingsFieldSheet } from "@/components/settings/SettingsFieldSheet";
import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsLinkRow,
  SettingsValueRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useModels } from "@/hooks/useModels";
import { api, type User } from "@/lib/api";
import { LANGUAGES } from "@/lib/i18n";
import { usageRemainingPercent } from "@/lib/quota";
import { getDisplayName, sanitizeDisplayName } from "@/lib/profile";
import { prefetchMemories } from "@/lib/memoryListCache";
import {
  connectedCountFromStatus,
  fetchIntegrationStatus,
  getCachedConnectedCount,
} from "@/lib/integrationStatusCache";
import { useTheme } from "@/lib/theme";

type ProfileField = "name" | "age" | "country" | "job";

export default function SettingsScreen() {
  const { token, user, signOut, updateUser } = useAuth();
  const { t } = useTranslation();
  const { isPro, autoEnabled, modelEnabledSet } = useModels();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const router = useRouter();

  const [usage, setUsage] = useState<Awaited<ReturnType<typeof api.todayUsage>> | null>(null);
  const [connectedCount, setConnectedCount] = useState(getCachedConnectedCount);
  const [upgradeVisible, setUpgradeVisible] = useState(false);
  const [editField, setEditField] = useState<ProfileField | null>(null);
  const [fieldText, setFieldText] = useState("");

  const refreshSummary = useCallback(async () => {
    if (!token) return;
    const [usageR, integrationsR] = await Promise.allSettled([
      api.todayUsage(token),
      fetchIntegrationStatus(token),
    ]);
    if (usageR.status === "fulfilled") setUsage(usageR.value);
    if (integrationsR.status === "fulfilled" && integrationsR.value) {
      setConnectedCount(connectedCountFromStatus(integrationsR.value));
    }
  }, [token]);

  useFocusEffect(
    useCallback(() => {
      void refreshSummary();
    }, [refreshSummary]),
  );

  const openField = (field: ProfileField) => {
    if (!user) return;
    const seed =
      field === "name"
        ? (user.name ?? "")
        : field === "age"
          ? user.age != null
            ? String(user.age)
            : ""
          : field === "country"
            ? (user.country ?? "")
            : (user.job ?? "");
    setFieldText(seed);
    setEditField(field);
  };

  const saveField = async () => {
    const field = editField;
    setEditField(null);
    if (!field || !user) return;

    let patch: Partial<User> | null = null;
    if (field === "name") {
      const name = sanitizeDisplayName(fieldText);
      if (!name || name === user.name) {
        if (fieldText.trim() && !name) {
          Alert.alert(t("common.error"), t("settings.name_invalid"));
        }
        return;
      }
      patch = { name };
    } else if (field === "age") {
      const trimmed = fieldText.trim();
      if (!trimmed) {
        if (user.age == null) return;
        patch = { age: null };
      } else {
        const age = Number.parseInt(trimmed, 10);
        if (!Number.isFinite(age) || age < 13 || age > 120) {
          Alert.alert(t("common.error"), t("settings.age_invalid"));
          return;
        }
        if (age === user.age) return;
        patch = { age };
      }
    } else if (field === "country") {
      const country = fieldText.trim() || null;
      if (country === (user.country ?? null)) return;
      patch = { country };
    } else {
      const job = fieldText.trim() || null;
      if (job === (user.job ?? null)) return;
      patch = { job };
    }

    try {
      await updateUser(patch);
    } catch {
      Alert.alert(t("common.error"), t("common.error"));
    }
  };

  if (!token) return <Redirect href="/login" />;

  const displayName = getDisplayName(user?.name, t("common.you"));
  const remainingPct = usage ? Math.round(usageRemainingPercent(usage)) : null;
  const accountLabel = isPro ? t("settings.account_pro") : t("settings.account_free");
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

  const fieldTitle =
    editField === "name"
      ? t("settings.your_name")
      : editField === "age"
        ? t("settings.your_age")
        : editField === "country"
          ? t("settings.your_country")
          : t("settings.your_job");
  const fieldPlaceholder =
    editField === "age"
      ? t("settings.age_placeholder")
      : editField === "country"
        ? t("settings.country_placeholder")
        : editField === "job"
          ? t("settings.job_placeholder")
          : undefined;
  const fieldMaxLength =
    editField === "name" ? 80 : editField === "country" ? 64 : editField === "job" ? 128 : 3;
  const fieldKeyboard =
    editField === "age" ? ("number-pad" as const) : ("default" as const);

  return (
    <View style={s.root}>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + 24 }]}
      >
        <View style={s.profileHeader}>
          <AvatarUsageRing
            name={user?.name ?? null}
            uri={user?.avatar_url}
            size={72}
            remainingPct={remainingPct}
          />
          <Text style={s.profileName}>{displayName}</Text>
          {user?.email ? (
            <Text style={s.profileEmail} numberOfLines={1}>
              {user.email}
            </Text>
          ) : null}
          <View style={[s.planPill, isPro && s.planPillPro]}>
            <Text style={[s.planPillText, isPro && s.planPillTextPro]}>
              {accountLabel}
            </Text>
          </View>
        </View>

        <SettingsGroup label={t("settings.profile")} styles={s}>
          <SettingsLinkRow
            icon="person-outline"
            title={t("settings.name_label")}
            value={displayName}
            onPress={() => openField("name")}
            styles={s}
            theme={theme}
          />
          <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
          <SettingsLinkRow
            icon="calendar-outline"
            title={t("settings.age_label")}
            value={user?.age != null ? String(user.age) : t("settings.not_set")}
            onPress={() => openField("age")}
            styles={s}
            theme={theme}
          />
          <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
          <SettingsLinkRow
            icon="flag-outline"
            title={t("settings.country_label")}
            value={user?.country?.trim() || t("settings.not_set")}
            onPress={() => openField("country")}
            styles={s}
            theme={theme}
          />
          <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
          <SettingsLinkRow
            icon="briefcase-outline"
            title={t("settings.job_label")}
            value={user?.job?.trim() || t("settings.not_set")}
            onPress={() => openField("job")}
            styles={s}
            theme={theme}
          />
          <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
          {isPro ? (
            <SettingsValueRow
              icon="diamond-outline"
              iconTone="warning"
              title={t("settings.account_label")}
              value={accountLabel}
              styles={s}
              theme={theme}
            />
          ) : (
            <SettingsLinkRow
              icon="diamond-outline"
              iconTone="warning"
              title={t("settings.account_label")}
              value={accountLabel}
              onPress={() => setUpgradeVisible(true)}
              styles={s}
              theme={theme}
            />
          )}
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
            iconTone="accent"
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
            iconTone="success"
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
            iconTone="warning"
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
            iconTone="accent"
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

      <SettingsFieldSheet
        visible={editField != null}
        title={fieldTitle}
        value={fieldText}
        onChangeText={setFieldText}
        onClose={() => setEditField(null)}
        onSave={() => void saveField()}
        maxLength={fieldMaxLength}
        placeholder={fieldPlaceholder}
        keyboardType={fieldKeyboard}
      />

      <UpgradeSheet visible={upgradeVisible} onClose={() => setUpgradeVisible(false)} />
    </View>
  );
}

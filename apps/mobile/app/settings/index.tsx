import { useCallback, useMemo, useState } from "react";
import {
  Alert,
  Modal,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { AvatarUsageRing } from "@/components/AvatarUsageRing";
import { UpgradeSheet } from "@/components/UpgradeSheet";
import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsLinkRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useModels } from "@/hooks/useModels";
import { api, type User } from "@/lib/api";
import { LANGUAGES } from "@/lib/i18n";
import { usageRemainingPercent } from "@/lib/quota";
import { getDisplayName, sanitizeDisplayName } from "@/lib/profile";
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
  const [connectedCount, setConnectedCount] = useState(0);
  const [upgradeVisible, setUpgradeVisible] = useState(false);
  const [editField, setEditField] = useState<ProfileField | null>(null);
  const [fieldText, setFieldText] = useState("");

  const refreshSummary = useCallback(async () => {
    if (!token) return;
    const [usageR, calendarR, gmailR] = await Promise.allSettled([
      api.todayUsage(token),
      api.googleCalendarStatus(token),
      api.googleGmailStatus(token),
    ]);
    if (usageR.status === "fulfilled") setUsage(usageR.value);
    let count = 0;
    if (calendarR.status === "fulfilled" && calendarR.value.connected) count += 1;
    if (gmailR.status === "fulfilled" && gmailR.value.connected) count += 1;
    setConnectedCount(count);
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
  const remainingPct = usageRemainingPercent(usage);
  const accountLabel = isPro ? t("settings.pro") : t("settings.free");
  const selectedLanguage =
    LANGUAGES.find((l) => l.code === (user?.locale ?? "en")) ?? LANGUAGES[0];
  const memoryValue = user?.memory_enabled ? t("settings.on") : t("settings.off");
  const modelsValue = autoEnabled
    ? t("settings.auto")
    : t("settings.models_count", { count: modelEnabledSet.size });
  const integrationsValue =
    connectedCount > 0
      ? t("settings.integrations_count", { count: connectedCount })
      : t("settings.none");

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
          <Text style={[s.profilePlan, isPro && s.accountPro]}>{accountLabel}</Text>
        </View>

        <SettingsGroup label={t("settings.profile")} styles={s}>
          <SettingsLinkRow
            title={t("settings.name_label")}
            value={displayName}
            onPress={() => openField("name")}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("settings.age_label")}
            value={user?.age != null ? String(user.age) : t("settings.not_set")}
            onPress={() => openField("age")}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("settings.country_label")}
            value={user?.country?.trim() || t("settings.not_set")}
            onPress={() => openField("country")}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("settings.job_label")}
            value={user?.job?.trim() || t("settings.not_set")}
            onPress={() => openField("job")}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <View style={s.menuRow}>
            <Text style={[s.rowTitle, s.menuRowTitle]}>{t("settings.email_label")}</Text>
            <Text style={s.linkValue} numberOfLines={1}>
              {user?.email}
            </Text>
          </View>
          <View style={s.menuSeparator} />
          {isPro ? (
            <View style={s.menuRow}>
              <Text style={[s.rowTitle, s.menuRowTitle]}>{t("settings.account_label")}</Text>
              <Text style={s.linkValue}>{accountLabel}</Text>
            </View>
          ) : (
            <SettingsLinkRow
              title={t("settings.account_label")}
              value={accountLabel}
              onPress={() => setUpgradeVisible(true)}
              styles={s}
              theme={theme}
            />
          )}
        </SettingsGroup>

        <SettingsGroup label={t("settings.general")} styles={s}>
          <SettingsLinkRow
            title={t("settings.model")}
            value={modelsValue}
            onPress={() => router.push("/settings/models")}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("settings.personalization")}
            value={selectedLanguage.label}
            onPress={() => router.push("/settings/preferences")}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("settings.learning.title")}
            onPress={() => router.push("/settings/learning")}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("settings.memory")}
            value={memoryValue}
            onPress={() => router.push("/settings/memory-settings")}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("settings.notifications")}
            value={user?.push_notifications_enabled ? t("settings.on") : t("settings.off")}
            onPress={() => router.push("/settings/notifications")}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("settings.integrations")}
            value={integrationsValue}
            onPress={() => router.push("/settings/integrations")}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>

        <SettingsGroup styles={s}>
          <SettingsLinkRow
            title={t("settings.data_controls")}
            onPress={() => router.push("/settings/data-controls")}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("settings.about")}
            onPress={() => router.push("/settings/about")}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>

        <Pressable
          style={s.signOut}
          onPress={async () => {
            await signOut();
            router.replace("/login");
          }}
        >
          <Text style={s.signOutText}>{t("settings.sign_out")}</Text>
        </Pressable>
      </ScrollView>

      <Modal
        visible={editField != null}
        transparent
        animationType="fade"
        onRequestClose={() => setEditField(null)}
      >
        <Pressable style={s.mOverlay} onPress={() => setEditField(null)}>
          <Pressable style={s.mSheet} onPress={(e) => e.stopPropagation()}>
            <Text style={s.mTitle}>{fieldTitle}</Text>
            <TextInput
              style={s.mInput}
              value={fieldText}
              onChangeText={setFieldText}
              autoFocus
              returnKeyType="done"
              onSubmitEditing={() => void saveField()}
              maxLength={fieldMaxLength}
              placeholder={fieldPlaceholder}
              placeholderTextColor={theme.textTertiary}
              keyboardType={fieldKeyboard}
            />
            <View style={s.mActions}>
              <Pressable style={s.mCancel} onPress={() => setEditField(null)}>
                <Text style={s.mCancelText}>{t("settings.cancel")}</Text>
              </Pressable>
              <Pressable style={s.mSave} onPress={() => void saveField()}>
                <Text style={s.mSaveText}>{t("settings.save")}</Text>
              </Pressable>
            </View>
          </Pressable>
        </Pressable>
      </Modal>

      <UpgradeSheet visible={upgradeVisible} onClose={() => setUpgradeVisible(false)} />
    </View>
  );
}

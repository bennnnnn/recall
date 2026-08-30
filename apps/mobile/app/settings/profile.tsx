import { useMemo, useRef, useState } from "react";
import { Alert, ScrollView, View } from "react-native";
import { Redirect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { UpgradeSheet } from "@/components/UpgradeSheet";
import { SettingsFieldSheet } from "@/components/settings/SettingsFieldSheet";
import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsLinkRow,
  SettingsValueRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useModels } from "@/hooks/useModels";
import { type User } from "@/lib/api";
import { getDisplayName, sanitizeDisplayName } from "@/lib/profile";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

type ProfileField = "name" | "age" | "country" | "job";

export default function ProfileSettingsScreen() {
  const { token, user, updateUser } = useAuth();
  const { t } = useTranslation();
  const { isPro } = useModels();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const feedback = useActionFeedbackOptional();

  const [upgradeVisible, setUpgradeVisible] = useState(false);
  const [editField, setEditField] = useState<ProfileField | null>(null);
  const [fieldText, setFieldText] = useState("");
  const [fieldSaving, setFieldSaving] = useState(false);
  const fieldSavingRef = useRef(false);

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
    if (fieldSavingRef.current) return;
    const field = editField;
    if (!field || !user) return;

    let patch: Partial<User> | null = null;
    if (field === "name") {
      const name = sanitizeDisplayName(fieldText);
      if (!name) {
        if (fieldText.trim()) Alert.alert(t("common.error"), t("settings.name_invalid"));
        return;
      }
      if (name === user.name) {
        setEditField(null);
        return;
      }
      patch = { name };
    } else if (field === "age") {
      const trimmed = fieldText.trim();
      if (!trimmed) {
        if (user.age == null) {
          setEditField(null);
          return;
        }
        patch = { age: null };
      } else {
        const age = Number.parseInt(trimmed, 10);
        if (!Number.isFinite(age) || age < 13 || age > 120) {
          Alert.alert(t("common.error"), t("settings.age_invalid"));
          return;
        }
        if (age === user.age) {
          setEditField(null);
          return;
        }
        patch = { age };
      }
    } else if (field === "country") {
      const country = fieldText.trim() || null;
      if (country === (user.country ?? null)) {
        setEditField(null);
        return;
      }
      patch = { country };
    } else {
      const job = fieldText.trim() || null;
      if (job === (user.job ?? null)) {
        setEditField(null);
        return;
      }
      patch = { job };
    }

    fieldSavingRef.current = true;
    setFieldSaving(true);
    try {
      await updateUser(patch);
      setEditField(null);
    } catch {
      if (feedback) feedback.error(t("common.error"));
      else Alert.alert(t("common.error"), t("common.error"));
    } finally {
      fieldSavingRef.current = false;
      setFieldSaving(false);
    }
  };

  if (!token) return <Redirect href="/login" />;

  const displayName = getDisplayName(user?.name, t("common.you"));
  const planLabel = isPro ? t("settings.account_pro") : t("settings.account_free");
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
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
      >
        <SettingsGroup styles={s}>
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
              title={t("settings.plan_label")}
              value={planLabel}
              styles={s}
              theme={theme}
            />
          ) : (
            <SettingsLinkRow
              icon="diamond-outline"
              title={t("settings.plan_label")}
              value={planLabel}
              onPress={() => setUpgradeVisible(true)}
              styles={s}
              theme={theme}
            />
          )}
        </SettingsGroup>
      </ScrollView>

      <SettingsFieldSheet
        visible={editField != null}
        title={fieldTitle}
        value={fieldText}
        onChangeText={setFieldText}
        onClose={() => setEditField(null)}
        onSave={() => void saveField()}
        saving={fieldSaving}
        maxLength={fieldMaxLength}
        placeholder={fieldPlaceholder}
        keyboardType={fieldKeyboard}
      />

      <UpgradeSheet
        visible={upgradeVisible}
        source="settings"
        onClose={() => setUpgradeVisible(false)}
      />
    </View>
  );
}

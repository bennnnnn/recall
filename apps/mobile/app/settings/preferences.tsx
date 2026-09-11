import { useCallback, useMemo, useRef, useState } from "react";
import { Alert, ScrollView, View } from "react-native";
import { Redirect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { SettingsFieldSheet } from "@/components/settings/SettingsFieldSheet";
import { SettingsPickerSheet } from "@/components/settings/SettingsPickerSheet";
import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsInlinePicker,
  SettingsLinkRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { LANGUAGES } from "@/lib/i18n";
import {
  DEFAULT_RESPONSE_TONE,
  normalizeResponseTone,
  RESPONSE_TONE_ORDER,
  RESPONSE_TONES,
} from "@/lib/responseTone";
import { type User } from "@/lib/api";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

const STYLES = ["short", "balanced", "detailed"] as const;
type AboutField = "age" | "country" | "job";

export default function PreferencesSettingsScreen() {
  const { token, user, updateUser } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const feedback = useActionFeedbackOptional();
  const [saving, setSaving] = useState(false);
  const [savingAction, setSavingAction] = useState<string | null>(null);
  const savingRef = useRef(false);
  const [openPicker, setOpenPicker] = useState<"style" | "tone" | null>(null);
  const [languageOpen, setLanguageOpen] = useState(false);
  const [instructionsOpen, setInstructionsOpen] = useState(false);
  const [instructionsText, setInstructionsText] = useState("");
  const [editField, setEditField] = useState<AboutField | null>(null);
  const [fieldText, setFieldText] = useState("");
  const [fieldSaving, setFieldSaving] = useState(false);
  const fieldSavingRef = useRef(false);

  const selectedLanguage =
    LANGUAGES.find((lang) => lang.code === user?.locale) ?? LANGUAGES[0];
  const selectedStyle = user?.response_style ?? "balanced";
  const selectedTone = normalizeResponseTone(user?.response_tone ?? DEFAULT_RESPONSE_TONE);

  const patch = useCallback(
    async (fields: Parameters<typeof updateUser>[0], action: string): Promise<boolean> => {
      if (savingRef.current) return false;
      savingRef.current = true;
      setSaving(true);
      setSavingAction(action);
      try {
        await updateUser(fields);
        return true;
      } catch {
        if (feedback) feedback.error(t("common.error"));
        else Alert.alert(t("common.error"), t("common.error"));
        return false;
      } finally {
        savingRef.current = false;
        setSaving(false);
        setSavingAction(null);
      }
    },
    [feedback, t, updateUser],
  );

  if (!token) return <Redirect href="/login" />;

  const openInstructions = () => {
    setInstructionsText(user?.custom_instructions ?? "");
    setInstructionsOpen(true);
  };

  const saveInstructions = async () => {
    const trimmed = instructionsText.trim();
    if ((user?.custom_instructions ?? null) === (trimmed || null)) {
      setInstructionsOpen(false);
      return;
    }
    const saved = await patch({ custom_instructions: trimmed || null }, "instructions");
    if (saved) setInstructionsOpen(false);
  };

  const openAbout = (field: AboutField) => {
    if (!user) return;
    const seed =
      field === "age"
        ? user.age != null
          ? String(user.age)
          : ""
        : field === "country"
          ? (user.country ?? "")
          : (user.job ?? "");
    setFieldText(seed);
    setEditField(field);
  };

  const saveAbout = async () => {
    if (fieldSavingRef.current || !user) return;
    const field = editField;
    if (!field) return;
    let patchBody: Partial<User> | null = null;
    if (field === "age") {
      const trimmed = fieldText.trim();
      if (!trimmed) {
        if (user.age == null) {
          setEditField(null);
          return;
        }
        patchBody = { age: null };
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
        patchBody = { age };
      }
    } else if (field === "country") {
      const country = fieldText.trim() || null;
      if (country === (user.country ?? null)) {
        setEditField(null);
        return;
      }
      patchBody = { country };
    } else {
      const job = fieldText.trim() || null;
      if (job === (user.job ?? null)) {
        setEditField(null);
        return;
      }
      patchBody = { job };
    }
    fieldSavingRef.current = true;
    setFieldSaving(true);
    try {
      await updateUser(patchBody);
      setEditField(null);
    } catch {
      if (feedback) feedback.error(t("common.error"));
      else Alert.alert(t("common.error"), t("common.error"));
    } finally {
      fieldSavingRef.current = false;
      setFieldSaving(false);
    }
  };

  const fieldTitle =
    editField === "age"
      ? t("settings.your_age")
      : editField === "country"
        ? t("settings.your_country")
        : t("settings.your_job");
  const fieldPlaceholder =
    editField === "age"
      ? t("settings.age_placeholder")
      : editField === "country"
        ? t("settings.country_placeholder")
        : t("settings.job_placeholder");

  return (
    <>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
      >
        <SettingsGroup label={t("settings.chat")} styles={s}>
          <SettingsInlinePicker
            title={t("settings.style")}
            subtitle={t("settings.style_summary")}
            value={t(`settings.style_${selectedStyle}`)}
            options={STYLES.map((st) => ({
              key: st,
              label: t(`settings.style_${st}`),
            }))}
            selectedKey={selectedStyle}
            expanded={openPicker === "style"}
            onToggle={() => setOpenPicker((cur) => (cur === "style" ? null : "style"))}
            onSelect={(st) =>
              void patch({ response_style: st as (typeof STYLES)[number] }, "style")
            }
            disabled={saving}
            busy={savingAction === "style"}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsInlinePicker
            title={t("settings.tone")}
            subtitle={t("settings.tone_hint")}
            value={t(`settings.tone_${selectedTone}`)}
            options={RESPONSE_TONE_ORDER.map((tone) => ({
              key: tone,
              label: t(`settings.tone_${tone}`),
            }))}
            selectedKey={selectedTone}
            expanded={openPicker === "tone"}
            onToggle={() => setOpenPicker((cur) => (cur === "tone" ? null : "tone"))}
            onSelect={(tone) =>
              void patch(
                { response_tone: tone as (typeof RESPONSE_TONES)[number] },
                "tone",
              )
            }
            disabled={saving}
            busy={savingAction === "tone"}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("settings.language")}
            subtitle={t("settings.language_summary")}
            value={selectedLanguage.label}
            onPress={() => setLanguageOpen(true)}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("settings.custom_instructions")}
            subtitle={t("settings.custom_instructions_summary")}
            value={
              user?.custom_instructions?.trim()
                ? t("settings.on")
                : t("settings.custom_instructions_none")
            }
            onPress={openInstructions}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>

        <SettingsGroup label={t("settings.about_you")} styles={s}>
          <SettingsLinkRow
            title={t("settings.age_label")}
            value={user?.age != null ? String(user.age) : t("settings.not_set")}
            onPress={() => openAbout("age")}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("settings.country_label")}
            value={user?.country?.trim() || t("settings.not_set")}
            onPress={() => openAbout("country")}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("settings.job_label")}
            value={user?.job?.trim() || t("settings.not_set")}
            onPress={() => openAbout("job")}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>
      </ScrollView>

      <SettingsPickerSheet
        visible={languageOpen}
        title={t("settings.language")}
        options={LANGUAGES.map((lang) => ({ key: lang.code, label: lang.label }))}
        selectedKey={user?.locale ?? selectedLanguage.code}
        onSelect={(code) => void patch({ locale: code }, "language")}
        onClose={() => setLanguageOpen(false)}
        busy={savingAction === "language"}
      />

      <SettingsFieldSheet
        visible={instructionsOpen}
        title={t("settings.custom_instructions")}
        hint={t("settings.custom_instructions_hint")}
        value={instructionsText}
        onChangeText={setInstructionsText}
        onClose={() => setInstructionsOpen(false)}
        onSave={() => void saveInstructions()}
        saving={savingAction === "instructions"}
        multiline
        maxLength={1000}
        placeholder={t("settings.custom_instructions_placeholder")}
      />

      <SettingsFieldSheet
        visible={editField != null}
        title={fieldTitle}
        value={fieldText}
        onChangeText={setFieldText}
        onClose={() => setEditField(null)}
        onSave={() => void saveAbout()}
        saving={fieldSaving}
        maxLength={editField === "country" ? 64 : editField === "job" ? 128 : 3}
        placeholder={fieldPlaceholder}
        keyboardType={editField === "age" ? "number-pad" : "default"}
      />
    </>
  );
}

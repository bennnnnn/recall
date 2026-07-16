import { useCallback, useMemo, useState } from "react";
import {
  Alert,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import { Redirect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { SettingsPickerModal } from "@/components/settings/SettingsPickerModal";
import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsLinkRow,
  SettingsSwitchRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { canUseDeviceLocation } from "@/lib/expoRuntime";
import { getDeviceLocationLabel } from "@/lib/deviceLocation";
import { LANGUAGES } from "@/lib/i18n";
import { DEFAULT_RESPONSE_TONE, normalizeResponseTone, RESPONSE_TONES } from "@/lib/responseTone";
import { APPEARANCE_OPTIONS } from "@/lib/appearance";
import { useAppearance } from "@/contexts/AppearanceContext";
import { useTheme } from "@/lib/theme";

const STYLES = ["short", "balanced", "detailed"] as const;

export default function PreferencesSettingsScreen() {
  const { token, user, updateUser } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const { preference: appearancePreference, setPreference: setAppearancePreference } =
    useAppearance();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const [saving, setSaving] = useState(false);
  const [appearancePickerOpen, setAppearancePickerOpen] = useState(false);
  const [languagePickerOpen, setLanguagePickerOpen] = useState(false);
  const [stylePickerOpen, setStylePickerOpen] = useState(false);
  const [tonePickerOpen, setTonePickerOpen] = useState(false);
  const [instructionsOpen, setInstructionsOpen] = useState(false);
  const [instructionsText, setInstructionsText] = useState("");

  const selectedLanguage =
    LANGUAGES.find((lang) => lang.code === user?.locale) ?? LANGUAGES[0];
  const selectedStyle = user?.response_style ?? "balanced";
  const selectedTone = normalizeResponseTone(user?.response_tone ?? DEFAULT_RESPONSE_TONE);

  const patch = useCallback(
    async (fields: Parameters<typeof updateUser>[0]) => {
      setSaving(true);
      try {
        await updateUser(fields);
      } finally {
        setSaving(false);
      }
    },
    [updateUser],
  );

  const handleLocationToggle = async (enabled: boolean) => {
    if (!enabled) {
      await patch({ location_enabled: false, location: null });
      return;
    }
    if (!canUseDeviceLocation()) {
      Alert.alert(t("settings.location"), t("settings.location_expo_go"));
      return;
    }
    setSaving(true);
    try {
      const label = await getDeviceLocationLabel();
      if (!label) {
        Alert.alert(t("settings.location"), t("settings.location_denied"));
        await updateUser({ location_enabled: false, location: null });
        return;
      }
      await updateUser({ location_enabled: true, location: label });
    } catch {
      Alert.alert(t("common.error"), t("settings.location_denied"));
    } finally {
      setSaving(false);
    }
  };

  const locationAvailable = canUseDeviceLocation();
  const locationEnabled = locationAvailable && (user?.location_enabled ?? false);
  const locationSubtitle = !locationAvailable
    ? t("settings.location_expo_go")
    : user?.location?.trim() || undefined;

  if (!token) return <Redirect href="/login" />;

  const openInstructions = () => {
    setInstructionsText(user?.custom_instructions ?? "");
    setInstructionsOpen(true);
  };

  const saveInstructions = async () => {
    setInstructionsOpen(false);
    const trimmed = instructionsText.trim();
    if ((user?.custom_instructions ?? null) === (trimmed || null)) return;
    await patch({ custom_instructions: trimmed || null });
  };

  return (
    <>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + 24 }]}
      >
        <SettingsGroup styles={s}>
          <SettingsLinkRow
            title={t("settings.appearance")}
            value={t(`settings.appearance_${appearancePreference}`)}
            onPress={() => setAppearancePickerOpen(true)}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("settings.style")}
            value={t(`settings.style_${selectedStyle}`)}
            onPress={() => setStylePickerOpen(true)}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("settings.tone")}
            value={t(`settings.tone_${selectedTone}`)}
            onPress={() => setTonePickerOpen(true)}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("settings.language")}
            value={selectedLanguage.label}
            onPress={() => setLanguagePickerOpen(true)}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsSwitchRow
            title={t("settings.location")}
            subtitle={locationSubtitle}
            value={locationEnabled}
            disabled={saving || !locationAvailable}
            onValueChange={(enabled) => void handleLocationToggle(enabled)}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("settings.custom_instructions")}
            value={user?.custom_instructions || t("settings.custom_instructions_none")}
            onPress={openInstructions}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>
      </ScrollView>

      <SettingsPickerModal
        visible={appearancePickerOpen}
        title={t("settings.appearance")}
        selectedKey={appearancePreference}
        options={APPEARANCE_OPTIONS.map((option) => ({
          key: option,
          label: t(`settings.appearance_${option}`),
        }))}
        onClose={() => setAppearancePickerOpen(false)}
        onSelect={(option) =>
          void setAppearancePreference(option as (typeof APPEARANCE_OPTIONS)[number])
        }
        styles={s}
        theme={theme}
      />
      <SettingsPickerModal
        visible={languagePickerOpen}
        title={t("settings.language")}
        selectedKey={user?.locale ?? selectedLanguage.code}
        options={LANGUAGES.map((lang) => ({ key: lang.code, label: lang.label }))}
        onClose={() => setLanguagePickerOpen(false)}
        onSelect={(code) => void patch({ locale: code })}
        disabled={saving}
        styles={s}
        theme={theme}
      />
      <SettingsPickerModal
        visible={stylePickerOpen}
        title={t("settings.style")}
        selectedKey={selectedStyle}
        options={STYLES.map((st) => ({ key: st, label: t(`settings.style_${st}`) }))}
        onClose={() => setStylePickerOpen(false)}
        onSelect={(st) => void patch({ response_style: st as (typeof STYLES)[number] })}
        disabled={saving}
        styles={s}
        theme={theme}
      />
      <SettingsPickerModal
        visible={tonePickerOpen}
        title={t("settings.tone")}
        selectedKey={selectedTone}
        options={RESPONSE_TONES.map((tone) => ({
          key: tone,
          label: t(`settings.tone_${tone}`),
        }))}
        onClose={() => setTonePickerOpen(false)}
        onSelect={(tone) =>
          void patch({ response_tone: tone as (typeof RESPONSE_TONES)[number] })
        }
        disabled={saving}
        styles={s}
        theme={theme}
      />
      <Modal visible={instructionsOpen} transparent animationType="fade">
        <KeyboardAvoidingView
          style={s.mKeyboardAvoider}
          behavior={Platform.OS === "ios" ? "padding" : undefined}
        >
          <Pressable style={s.mOverlay} onPress={() => setInstructionsOpen(false)}>
            <Pressable style={s.mSheet} onPress={(e) => e.stopPropagation()}>
              <Text style={s.mTitle}>{t("settings.custom_instructions")}</Text>
              <Text style={s.sectionHint}>{t("settings.custom_instructions_hint")}</Text>
              <TextInput
                style={[s.mInput, { minHeight: 96, textAlignVertical: "top" }]}
                value={instructionsText}
                onChangeText={setInstructionsText}
                autoFocus
                multiline
                maxLength={1000}
                placeholder={t("settings.custom_instructions_placeholder")}
                placeholderTextColor={theme.textTertiary}
              />
              <View style={s.mActions}>
                <Pressable style={s.mCancel} onPress={() => setInstructionsOpen(false)}>
                  <Text style={s.mCancelText}>{t("settings.cancel")}</Text>
                </Pressable>
                <Pressable style={s.mSave} onPress={() => void saveInstructions()}>
                  <Text style={s.mSaveText}>{t("settings.save")}</Text>
                </Pressable>
              </View>
            </Pressable>
          </Pressable>
        </KeyboardAvoidingView>
      </Modal>
    </>
  );
}

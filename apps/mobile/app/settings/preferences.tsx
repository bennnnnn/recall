import { useCallback, useMemo, useRef, useState } from "react";
import { Alert, ScrollView, View } from "react-native";
import { Redirect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { SettingsFieldSheet } from "@/components/settings/SettingsFieldSheet";
import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsInlinePicker,
  SettingsLinkRow,
  SettingsSwitchRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { canUseDeviceLocation } from "@/lib/expoRuntime";
import { getDeviceLocationLabel } from "@/lib/deviceLocation";
import { LANGUAGES } from "@/lib/i18n";
import { DEFAULT_RESPONSE_TONE, normalizeResponseTone, RESPONSE_TONES } from "@/lib/responseTone";
import { APPEARANCE_OPTIONS } from "@/lib/appearance";
import { useAppearance } from "@/contexts/AppearanceContext";
import { Space } from "@/lib/space";
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
  const feedback = useActionFeedbackOptional();
  const [saving, setSaving] = useState(false);
  const [savingAction, setSavingAction] = useState<string | null>(null);
  const savingRef = useRef(false);
  const [openPicker, setOpenPicker] = useState<
    "appearance" | "style" | "tone" | "language" | null
  >(null);
  const [instructionsOpen, setInstructionsOpen] = useState(false);
  const [instructionsText, setInstructionsText] = useState("");

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

  const handleLocationToggle = async (enabled: boolean) => {
    if (!enabled) {
      await patch({ location_enabled: false, location: null }, "location");
      return;
    }
    if (!canUseDeviceLocation()) {
      Alert.alert(t("settings.location"), t("settings.location_expo_go"));
      return;
    }
    if (savingRef.current) return;
    savingRef.current = true;
    setSaving(true);
    setSavingAction("location");
    try {
      const label = await getDeviceLocationLabel();
      if (!label) {
        Alert.alert(t("settings.location"), t("settings.location_denied"));
        await updateUser({ location_enabled: false, location: null });
        return;
      }
      await updateUser({ location_enabled: true, location: label });
    } catch {
      if (feedback) feedback.error(t("settings.location_denied"));
      else Alert.alert(t("common.error"), t("settings.location_denied"));
    } finally {
      savingRef.current = false;
      setSaving(false);
      setSavingAction(null);
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
    const trimmed = instructionsText.trim();
    if ((user?.custom_instructions ?? null) === (trimmed || null)) {
      setInstructionsOpen(false);
      return;
    }
    const saved = await patch(
      { custom_instructions: trimmed || null },
      "instructions",
    );
    if (saved) setInstructionsOpen(false);
  };

  return (
    <>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
      >
        <SettingsGroup label={t("settings.appearance")} styles={s}>
          <SettingsInlinePicker
            icon="contrast-outline"
            title={t("settings.appearance")}
            subtitle={t("settings.appearance_summary")}
            value={t(`settings.appearance_${appearancePreference}`)}
            options={APPEARANCE_OPTIONS.map((option) => ({
              key: option,
              label: t(`settings.appearance_${option}`),
            }))}
            selectedKey={appearancePreference}
            expanded={openPicker === "appearance"}
            onToggle={() =>
              setOpenPicker((cur) => (cur === "appearance" ? null : "appearance"))
            }
            onSelect={(option) =>
              void setAppearancePreference(option as (typeof APPEARANCE_OPTIONS)[number])
            }
            styles={s}
            theme={theme}
          />
        </SettingsGroup>

        <SettingsGroup label={t("settings.chat")} styles={s}>
          <SettingsInlinePicker
            icon="text-outline"
            title={t("settings.style")}
            subtitle={t("settings.style_summary")}
            value={t(`settings.style_${selectedStyle}`)}
            options={STYLES.map((st) => ({
              key: st,
              label: t(`settings.style_${st}`),
            }))}
            selectedKey={selectedStyle}
            expanded={openPicker === "style"}
            onToggle={() =>
              setOpenPicker((cur) => (cur === "style" ? null : "style"))
            }
            onSelect={(st) =>
              void patch({ response_style: st as (typeof STYLES)[number] }, "style")
            }
            disabled={saving}
            busy={savingAction === "style"}
            styles={s}
            theme={theme}
          />
          <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
          <SettingsInlinePicker
            icon="chatbubble-ellipses-outline"
            title={t("settings.tone")}
            subtitle={t("settings.tone_hint")}
            value={t(`settings.tone_${selectedTone}`)}
            options={RESPONSE_TONES.map((tone) => ({
              key: tone,
              label: t(`settings.tone_${tone}`),
            }))}
            selectedKey={selectedTone}
            expanded={openPicker === "tone"}
            onToggle={() =>
              setOpenPicker((cur) => (cur === "tone" ? null : "tone"))
            }
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
          <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
          <SettingsInlinePicker
            icon="globe-outline"
            title={t("settings.language")}
            subtitle={t("settings.language_summary")}
            value={selectedLanguage.label}
            options={LANGUAGES.map((lang) => ({
              key: lang.code,
              label: lang.label,
            }))}
            selectedKey={user?.locale ?? selectedLanguage.code}
            expanded={openPicker === "language"}
            onToggle={() =>
              setOpenPicker((cur) => (cur === "language" ? null : "language"))
            }
            onSelect={(code) => void patch({ locale: code }, "language")}
            disabled={saving}
            busy={savingAction === "language"}
            styles={s}
            theme={theme}
          />
          <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
          <SettingsLinkRow
            icon="create-outline"
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

        <SettingsGroup label={t("settings.location")} styles={s}>
          <SettingsSwitchRow
            icon="location-outline"
            title={t("settings.location")}
            subtitle={locationSubtitle}
            value={locationEnabled}
            disabled={saving || !locationAvailable}
            busy={savingAction === "location"}
            onValueChange={(enabled) => void handleLocationToggle(enabled)}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>
      </ScrollView>

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
    </>
  );
}

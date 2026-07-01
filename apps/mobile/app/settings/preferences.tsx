import { useCallback, useMemo, useState } from "react";
import { Alert, ScrollView, View } from "react-native";
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
import { useTheme } from "@/lib/theme";

const STYLES = ["short", "balanced", "detailed"] as const;

export default function PreferencesSettingsScreen() {
  const { token, user, updateUser } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const [saving, setSaving] = useState(false);
  const [languagePickerOpen, setLanguagePickerOpen] = useState(false);
  const [stylePickerOpen, setStylePickerOpen] = useState(false);
  const [tonePickerOpen, setTonePickerOpen] = useState(false);

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

  if (!token) return <Redirect href="/login" />;

  return (
    <>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + 24 }]}
      >
        <SettingsGroup styles={s}>
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
            value={user?.location_enabled ?? false}
            disabled={saving}
            onValueChange={(enabled) => void handleLocationToggle(enabled)}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>
      </ScrollView>

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
    </>
  );
}

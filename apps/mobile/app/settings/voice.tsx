import { useMemo, useState } from "react";
import { ScrollView } from "react-native";
import { Redirect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsInlinePicker,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useTtsPreference } from "@/hooks/useTtsPreference";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";
import { TTS_DEVICE_MODEL, TTS_QUALITY_MODEL } from "@/lib/ttsPreference";

export default function VoiceSettingsScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const { ttsModel, selectTtsModel } = useTtsPreference();
  const [expanded, setExpanded] = useState(true);

  if (!token) return <Redirect href="/login" />;

  return (
    <ScrollView
      style={s.scroll}
      contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
    >
      <SettingsGroup styles={s}>
        <SettingsInlinePicker
          title={t("settings.voice")}
          subtitle={t("settings.voice_summary")}
          value={
            ttsModel === TTS_DEVICE_MODEL
              ? t("settings.tts_device_voice")
              : t("settings.tts_enhanced_voice")
          }
          options={[
            { key: TTS_DEVICE_MODEL, label: t("settings.tts_device_voice") },
            { key: TTS_QUALITY_MODEL, label: t("settings.tts_enhanced_voice") },
          ]}
          selectedKey={ttsModel}
          expanded={expanded}
          onToggle={() => setExpanded((open) => !open)}
          onSelect={(key) =>
            selectTtsModel(key === TTS_DEVICE_MODEL ? TTS_DEVICE_MODEL : TTS_QUALITY_MODEL)
          }
          styles={s}
          theme={theme}
        />
      </SettingsGroup>
    </ScrollView>
  );
}

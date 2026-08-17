import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, ScrollView, Switch, Text, View } from "react-native";
import { Redirect, useFocusEffect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { UpgradeSheet } from "@/components/UpgradeSheet";
import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsSwitchRow,
  SettingsValueRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { buildModelPreferences, useModels } from "@/hooks/useModels";
import { useTtsPreference } from "@/hooks/useTtsPreference";
import { api, type Usage } from "@/lib/api";
import {
  formatTokenCount,
  promptWindowMessages,
  promptWindowTokens,
  usageUsedTokens,
} from "@/lib/quota";
import { useTheme } from "@/lib/theme";
import { TTS_DEVICE_MODEL, TTS_FAST_MODEL, TTS_QUALITY_MODEL } from "@/lib/ttsPreference";

function sameIdSet(a: Set<string>, b: Set<string>): boolean {
  if (a.size !== b.size) return false;
  for (const id of a) {
    if (!b.has(id)) return false;
  }
  return true;
}

type DraftPrefs = {
  auto: boolean;
  models: Set<string>;
};

export default function ModelsSettingsScreen() {
  const { token, user, updateUser } = useAuth();
  const { t } = useTranslation();
  const {
    models,
    isPro,
    autoEnabled,
    modelEnabledSet,
  } = useModels();
  const { ttsModel, selectTtsModel } = useTtsPreference();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const [upgradeVisible, setUpgradeVisible] = useState(false);
  const [usage, setUsage] = useState<Usage | null>(null);
  // Local draft so the Switch doesn't snap back while Auth/Models context
  // catches up (and so a racing /auth/me echo can't flash the old value).
  const [draft, setDraft] = useState<DraftPrefs | null>(null);

  const refreshUsage = useCallback(async () => {
    if (!token) return;
    try {
      setUsage(await api.todayUsage(token));
    } catch {
      // Keep the last successful read; defaults still render the window.
    }
  }, [token]);

  useFocusEffect(
    useCallback(() => {
      void refreshUsage();
    }, [refreshUsage]),
  );

  const effectiveAuto = draft?.auto ?? autoEnabled;
  const effectiveModels = draft?.models ?? modelEnabledSet;

  useEffect(() => {
    if (!draft) return;
    if (draft.auto === autoEnabled && sameIdSet(draft.models, modelEnabledSet)) {
      setDraft(null);
    }
  }, [autoEnabled, modelEnabledSet, draft]);

  if (!token) return <Redirect href="/login" />;

  const patchPreferences = (auto: boolean, modelIds: Set<string>) => {
    if (!auto && modelIds.size === 0) return;
    const nextModels = new Set(modelIds);
    setDraft({ auto, models: nextModels });
    void updateUser({ enabled_models: buildModelPreferences(auto, nextModels) }).catch(
      () => {
        setDraft(null);
        Alert.alert(t("common.error"));
      },
    );
  };

  const toggleAuto = (enabled: boolean) => {
    if (!enabled && effectiveModels.size === 0) return;
    patchPreferences(enabled, effectiveModels);
  };

  const toggleModel = (modelId: string, enabled: boolean) => {
    if (!user) return;
    const option = models.find((m) => m.id === modelId);
    if (!option?.available) return;
    if (!isPro && option.plan_access === "pro") {
      if (enabled) setUpgradeVisible(true);
      return;
    }
    const next = new Set(effectiveModels);
    if (enabled) next.add(modelId);
    else next.delete(modelId);
    if (next.size === 0 && !effectiveAuto) return;
    patchPreferences(effectiveAuto, next);
  };

  return (
    <>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + 24 }]}
      >
        <SettingsGroup label={t("settings.usage_group")} styles={s}>
          <SettingsValueRow
            icon="speedometer-outline"
            title={t("settings.usage_today")}
            value={
              usage
                ? t("settings.usage_today_value", {
                    used: formatTokenCount(usageUsedTokens(usage)),
                    limit: formatTokenCount(usage.daily_limit),
                  })
                : undefined
            }
            subtitle={
              usage
                ? t("settings.usage_today_split", {
                    input: formatTokenCount(usage.input_tokens),
                    output: formatTokenCount(usage.output_tokens),
                  })
                : undefined
            }
            styles={s}
            theme={theme}
          />
          <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
          <SettingsValueRow
            icon="layers-outline"
            title={t("settings.prompt_window")}
            value={t("settings.prompt_window_value", {
              tokens: formatTokenCount(promptWindowTokens(usage)),
            })}
            subtitle={t("settings.prompt_window_summary", {
              count: promptWindowMessages(usage),
            })}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>

        <SettingsGroup styles={s}>
          <SettingsSwitchRow
            icon="flash-outline"
            title={t("settings.model_auto")}
            subtitle={t("settings.model_auto_summary")}
            value={effectiveAuto}
            disabled={effectiveAuto && effectiveModels.size === 0}
            onValueChange={toggleAuto}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>

        <SettingsGroup label={t("settings.model")} styles={s}>
          {models.map((option, index) => {
            const proLocked = !isPro && option.plan_access === "pro";
            const enabled = effectiveModels.has(option.id) && !proLocked;
            const isLastModel = enabled && effectiveModels.size <= 1 && !effectiveAuto;
            const switchDisabled =
              isLastModel || (!enabled && !option.available && !proLocked);

            return (
              <View key={option.id}>
                {index > 0 ? <View style={s.menuSeparator} /> : null}
                <View style={s.menuRow}>
                  <View style={s.rowBody}>
                    <Text style={s.rowTitle}>{option.label}</Text>
                    {proLocked ? (
                      <Text style={s.meta}>{t("settings.account_pro")}</Text>
                    ) : null}
                    {!proLocked && option.healthy === false ? (
                      <Text style={s.meta}>{t("settings.model_degraded")}</Text>
                    ) : null}
                    {!proLocked &&
                    option.healthy !== false &&
                    option.latency_p50_ms != null &&
                    option.latency_p50_ms > 0 ? (
                      <Text style={s.meta}>
                        {t("settings.model_latency", { ms: option.latency_p50_ms })}
                      </Text>
                    ) : null}
                  </View>
                  <Switch
                    value={enabled}
                    disabled={switchDisabled}
                    thumbColor={theme.bg}
                    trackColor={{ false: theme.border, true: theme.primary }}
                    onValueChange={(v) => {
                      if (proLocked) {
                        if (v) setUpgradeVisible(true);
                        return;
                      }
                      if (v && !option.available) return;
                      toggleModel(option.id, v);
                    }}
                  />
                </View>
              </View>
            );
          })}
        </SettingsGroup>

        <SettingsGroup label={t("settings.tts")} styles={s}>
          <SettingsSwitchRow
            icon="phone-portrait-outline"
            title={t("settings.tts_device")}
            subtitle={t("settings.tts_device_meta")}
            value={ttsModel === TTS_DEVICE_MODEL}
            onValueChange={(enabled) => {
              if (enabled) selectTtsModel(TTS_DEVICE_MODEL);
            }}
            styles={s}
            theme={theme}
          />
          <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
          <SettingsSwitchRow
            icon="volume-high-outline"
            title={t("settings.tts_gemini")}
            subtitle={t("settings.tts_gemini_meta")}
            value={ttsModel === TTS_QUALITY_MODEL}
            onValueChange={(enabled) => {
              if (enabled) selectTtsModel(TTS_QUALITY_MODEL);
            }}
            styles={s}
            theme={theme}
          />
          <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
          <SettingsSwitchRow
            icon="volume-medium-outline"
            title={t("settings.tts_kokoro")}
            subtitle={t("settings.tts_kokoro_meta")}
            value={ttsModel === TTS_FAST_MODEL}
            onValueChange={(enabled) => {
              if (enabled) selectTtsModel(TTS_FAST_MODEL);
            }}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>
      </ScrollView>
      <UpgradeSheet visible={upgradeVisible} onClose={() => setUpgradeVisible(false)} />
    </>
  );
}

import { useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Alert, ScrollView, Switch, Text, View } from "react-native";
import { Redirect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { UpgradeSheet } from "@/components/UpgradeSheet";
import {
  makeSettingsStyles,
  SettingsDisclosureRow,
  SettingsGroup,
  SettingsSwitchRow,
  SettingsValueRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { buildModelPreferences, useModels } from "@/hooks/useModels";
import { useUsage } from "@/hooks/useUsage";
import {
  formatTokenCount,
  promptWindowMessages,
  promptWindowTokens,
  usageUsedTokens,
} from "@/lib/quota";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

function sameIdSet(a: Set<string>, b: Set<string>): boolean {
  if (a.size !== b.size) return false;
  for (const id of a) {
    if (!b.has(id)) {
      return false;
    }
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
  const { models, isPro, autoEnabled, modelEnabledSet } = useModels();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const [upgradeVisible, setUpgradeVisible] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const usage = useUsage();
  const [draft, setDraft] = useState<DraftPrefs | null>(null);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const savingRef = useRef(false);
  const feedback = useActionFeedbackOptional();

  const effectiveAuto = draft?.auto ?? autoEnabled;
  const effectiveModels = draft?.models ?? modelEnabledSet;

  useEffect(() => {
    if (!draft) return;
    if (draft.auto === autoEnabled && sameIdSet(draft.models, modelEnabledSet)) {
      setDraft(null);
    }
  }, [autoEnabled, modelEnabledSet, draft]);

  if (!token) return <Redirect href="/login" />;

  const patchPreferences = (auto: boolean, modelIds: Set<string>, key: string) => {
    if ((!auto && modelIds.size === 0) || savingRef.current) return;
    savingRef.current = true;
    setSavingKey(key);
    const nextModels = new Set(modelIds);
    setDraft({ auto, models: nextModels });
    void updateUser({ enabled_models: buildModelPreferences(auto, nextModels) })
      .catch(() => {
        setDraft(null);
        if (feedback) feedback.error(t("common.error"));
        else Alert.alert(t("common.error"));
      })
      .finally(() => {
        savingRef.current = false;
        setSavingKey(null);
      });
  };

  const toggleAuto = (enabled: boolean) => {
    if (!enabled && effectiveModels.size === 0) return;
    patchPreferences(enabled, effectiveModels, "auto");
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
    patchPreferences(effectiveAuto, next, modelId);
  };

  const used = usage ? usageUsedTokens(usage) : 0;
  const limit = usage?.daily_limit ?? 0;
  const usagePct = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;

  return (
    <>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
      >
        <SettingsGroup label={t("settings.usage_group")} styles={s}>
          <View style={s.menuRow}>
            <View style={s.rowBody}>
              <Text style={s.rowTitle}>{t("settings.usage_daily")}</Text>
              <Text style={s.meta}>
                {usage
                  ? t("settings.usage_today_value", {
                      used: formatTokenCount(used),
                      limit: formatTokenCount(limit),
                    })
                  : " "}
              </Text>
              <View
                style={s.usageTrack}
                accessibilityRole="progressbar"
                accessibilityValue={{ min: 0, max: 100, now: usagePct }}
              >
                <View style={[s.usageFill, { width: `${usagePct}%` }]} />
              </View>
            </View>
          </View>
        </SettingsGroup>

        <SettingsGroup styles={s}>
          <SettingsSwitchRow
            title={t("settings.model_auto")}
            subtitle={t("settings.model_auto_summary")}
            value={effectiveAuto}
            disabled={Boolean(savingKey) || (effectiveAuto && effectiveModels.size === 0)}
            busy={savingKey === "auto"}
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
                  </View>
                  {savingKey === option.id ? (
                    <ActivityIndicator
                      size="small"
                      color={theme.primary}
                      accessibilityRole="progressbar"
                    />
                  ) : (
                    <Switch
                      value={enabled}
                      disabled={Boolean(savingKey) || switchDisabled}
                      thumbColor={theme.bg}
                      trackColor={{ false: theme.border, true: theme.primary }}
                      accessibilityState={{
                        disabled: Boolean(savingKey) || switchDisabled,
                        busy: false,
                      }}
                      onValueChange={(v) => {
                        if (proLocked) {
                          if (v) setUpgradeVisible(true);
                          return;
                        }
                        if (v && !option.available) return;
                        toggleModel(option.id, v);
                      }}
                    />
                  )}
                </View>
              </View>
            );
          })}
        </SettingsGroup>

        {__DEV__ ? (
          <SettingsGroup styles={s}>
            <SettingsDisclosureRow
              title={t("settings.advanced")}
              expanded={advancedOpen}
              onToggle={() => setAdvancedOpen((open) => !open)}
              styles={s}
              theme={theme}
            />
            {advancedOpen ? (
              <>
                <View style={s.menuSeparator} />
                <SettingsValueRow
                  title={t("settings.usage_split")}
                  value={
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
                <View style={s.menuSeparator} />
                <SettingsValueRow
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
                {models.map((option) =>
                  option.latency_p50_ms != null && option.latency_p50_ms > 0 ? (
                    <View key={`latency-${option.id}`}>
                      <View style={s.menuSeparator} />
                      <SettingsValueRow
                        title={option.label}
                        value={t("settings.model_latency", {
                          ms: option.latency_p50_ms,
                        })}
                        styles={s}
                        theme={theme}
                      />
                    </View>
                  ) : null,
                )}
              </>
            ) : null}
          </SettingsGroup>
        ) : null}
      </ScrollView>
      <UpgradeSheet
        visible={upgradeVisible}
        source="model_gate"
        onClose={() => setUpgradeVisible(false)}
      />
    </>
  );
}

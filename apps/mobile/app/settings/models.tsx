import { useEffect, useMemo, useRef, useState } from "react";
import { ScrollView, View } from "react-native";
import { Redirect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { UpgradeSheet } from "@/components/UpgradeSheet";
import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsSwitchRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { buildModelPreferences, useModels } from "@/hooks/useModels";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";
import { reportRecoverableError } from "@/lib/reportRecoverableError";

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
        reportRecoverableError(feedback, t("common.error"));
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

  return (
    <>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
      >
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

        <SettingsGroup styles={s}>
          {models.map((option, index) => {
            const proLocked = !isPro && option.plan_access === "pro";
            const enabled = effectiveModels.has(option.id) && !proLocked;
            const isLastModel = enabled && effectiveModels.size <= 1 && !effectiveAuto;
            const switchDisabled =
              isLastModel || (!enabled && !option.available && !proLocked);

            return (
              <View key={option.id}>
                {index > 0 ? <View style={s.menuSeparator} /> : null}
                <SettingsSwitchRow
                  title={option.label}
                  subtitle={
                    proLocked
                      ? t("settings.account_pro")
                      : option.healthy === false
                        ? t("settings.model_degraded")
                        : undefined
                  }
                  value={enabled}
                  disabled={Boolean(savingKey) || switchDisabled}
                  busy={savingKey === option.id}
                  onValueChange={(value) => toggleModel(option.id, value)}
                  styles={s}
                  theme={theme}
                />
              </View>
            );
          })}
        </SettingsGroup>
      </ScrollView>
      <UpgradeSheet
        visible={upgradeVisible}
        source="model_gate"
        onClose={() => setUpgradeVisible(false)}
      />
    </>
  );
}

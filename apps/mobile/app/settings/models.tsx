import { useCallback, useMemo, useState } from "react";
import { ScrollView, Switch, Text, View } from "react-native";
import { Redirect, useFocusEffect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { UpgradeSheet } from "@/components/UpgradeSheet";
import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsSwitchRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { buildModelPreferences, useModels } from "@/hooks/useModels";
import { useTheme } from "@/lib/theme";

export default function ModelsSettingsScreen() {
  const { token, user, updateUser } = useAuth();
  const { t } = useTranslation();
  const {
    models,
    isPro,
    autoEnabled,
    modelEnabledSet,
    refresh: refreshModels,
  } = useModels();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const [upgradeVisible, setUpgradeVisible] = useState(false);

  useFocusEffect(
    useCallback(() => {
      if (!token) return;
      void refreshModels();
    }, [refreshModels, token]),
  );

  if (!token) return <Redirect href="/login" />;

  const patchPreferences = (auto: boolean, modelIds: Set<string>) => {
    if (!auto && modelIds.size === 0) return;
    void updateUser({ enabled_models: buildModelPreferences(auto, modelIds) }).catch(() => {});
  };

  const toggleAuto = (enabled: boolean) => {
    if (!enabled && modelEnabledSet.size === 0) return;
    patchPreferences(enabled, modelEnabledSet);
  };

  const toggleModel = (modelId: string, enabled: boolean) => {
    if (!user) return;
    const option = models.find((m) => m.id === modelId);
    if (!option?.available) return;
    if (!isPro && option.plan_access === "pro") {
      if (enabled) setUpgradeVisible(true);
      return;
    }
    const next = new Set(modelEnabledSet);
    if (enabled) next.add(modelId);
    else next.delete(modelId);
    if (next.size === 0 && !autoEnabled) return;
    patchPreferences(autoEnabled, next);
  };

  return (
    <>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + 24 }]}
      >
        <SettingsGroup styles={s}>
          <SettingsSwitchRow
            title={t("settings.model_auto")}
            value={autoEnabled}
            disabled={autoEnabled && modelEnabledSet.size === 0}
            onValueChange={toggleAuto}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>

        <SettingsGroup label={t("settings.model")} styles={s}>
          {models.map((option, index) => {
            const proLocked = !isPro && option.plan_access === "pro";
            const enabled = modelEnabledSet.has(option.id) && !proLocked;
            const isLastModel = enabled && modelEnabledSet.size <= 1 && !autoEnabled;
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
      </ScrollView>
      <UpgradeSheet visible={upgradeVisible} onClose={() => setUpgradeVisible(false)} />
    </>
  );
}

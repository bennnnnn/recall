import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { UpgradeSheet } from "@/features/billing/components/UpgradeSheet";
import {
  SettingsGroup,
  SettingsMenuRow,
  SettingsPage,
  SettingsSwitchRow,
  SettingsValueRow,
} from "@/features/account/components/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { buildModelPreferences, useModels } from "@/hooks/useModels";
import { planNameKey } from "@/lib/plan";
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

/** A model row's line under its name: why its switch cannot move, or that it is degraded. */
function modelRowNote(
  t: (key: string) => string,
  row: { proLocked: boolean; isLastModel: boolean; degraded: boolean },
): string | undefined {
  if (row.proLocked) return t(planNameKey("plus"));
  if (row.isLastModel) return t("settings.model_last_on");
  return row.degraded ? t("settings.model_degraded") : undefined;
}

type DraftPrefs = {
  auto: boolean;
  models: Set<string>;
};

export default function ModelsSettingsScreen() {
  const { user, updateUser } = useAuth();
  const { t } = useTranslation();
  const { models, isPaid, autoEnabled, modelEnabledSet } = useModels();
  const [upgradeVisible, setUpgradeVisible] = useState(false);
  const [draft, setDraft] = useState<DraftPrefs | null>(null);
  const feedback = useActionFeedbackOptional();

  const effectiveAuto = draft?.auto ?? autoEnabled;
  const effectiveModels = draft?.models ?? modelEnabledSet;
  // Something must answer: Auto, or at least one model.
  const autoLocked = effectiveAuto && effectiveModels.size === 0;

  useEffect(() => {
    if (!draft) return;
    if (draft.auto === autoEnabled && sameIdSet(draft.models, modelEnabledSet)) {
      setDraft(null);
    }
  }, [autoEnabled, modelEnabledSet, draft]);

  // Each tap shows at once and saves; saves run in order (AuthContext.updateUser), so taps
  // made while one saves are never dropped and the last one is what the account keeps.
  const patchPreferences = (auto: boolean, modelIds: Set<string>) => {
    if (!auto && modelIds.size === 0) return;
    const pending: DraftPrefs = { auto, models: new Set(modelIds) };
    setDraft(pending);
    void updateUser({ enabled_models: buildModelPreferences(auto, pending.models) }).catch(() => {
      // Back to the account's saved switches, unless a later tap has moved them since.
      setDraft((current) => (current === pending ? null : current));
      reportRecoverableError(feedback, t("common.error"));
    });
  };

  const toggleAuto = (enabled: boolean) => {
    if (!enabled && effectiveModels.size === 0) return;
    patchPreferences(enabled, effectiveModels);
  };

  /** With Auto off, every message goes to the first model switched on; this puts `modelId` first. */
  const chooseModelInUse = (modelId: string) => {
    const rest = [...effectiveModels].filter((id) => id !== modelId);
    patchPreferences(false, new Set([modelId, ...rest]));
  };
  const usable = models.filter(
    (option) => effectiveModels.has(option.id) && (isPaid || option.plan_access !== "pro"),
  );
  const inUse = usable.find((option) => option.id === [...effectiveModels][0]) ?? usable[0];

  const toggleModel = (modelId: string, enabled: boolean) => {
    if (!user) return;
    const option = models.find((m) => m.id === modelId);
    if (!option?.available) return;
    if (!isPaid && option.plan_access === "pro") {
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
      <SettingsPage>
        <SettingsGroup>
          <SettingsSwitchRow
            title={t("settings.model_auto")}
            // A switch that cannot move says why, not only by looking pale.
            subtitle={t(autoLocked ? "settings.model_auto_needs_model" : "settings.model_auto_summary")}
            value={effectiveAuto}
            disabled={autoLocked}
            onValueChange={toggleAuto}
          />
          {!effectiveAuto && inUse ? (
            usable.length > 1 ? (
              <SettingsMenuRow
                title={t("settings.model_in_use")}
                subtitle={t("settings.model_in_use_summary")}
                value={inUse.label}
                options={usable.map((option) => ({ key: option.id, label: option.label }))}
                selectedKey={inUse.id}
                onSelect={chooseModelInUse}
              />
            ) : (
              <SettingsValueRow
                title={t("settings.model_in_use")}
                subtitle={t("settings.model_in_use_summary")}
                value={inUse.label}
              />
            )
          ) : null}
        </SettingsGroup>

        <SettingsGroup label={t("settings.models_list")}>
          {models.map((option) => {
            const proLocked = !isPaid && option.plan_access === "pro";
            const enabled = effectiveModels.has(option.id) && !proLocked;
            const isLastModel = enabled && effectiveModels.size <= 1 && !effectiveAuto;
            const switchDisabled =
              isLastModel || (!enabled && !option.available && !proLocked);

            return (
              <SettingsSwitchRow
                key={option.id}
                title={option.label}
                subtitle={modelRowNote(t, { proLocked, isLastModel, degraded: option.healthy === false })}
                value={enabled}
                disabled={switchDisabled}
                onValueChange={(value) => toggleModel(option.id, value)}
              />
            );
          })}
        </SettingsGroup>
      </SettingsPage>
      <UpgradeSheet
        visible={upgradeVisible}
        source="model_gate"
        onClose={() => setUpgradeVisible(false)}
      />
    </>
  );
}

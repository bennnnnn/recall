import { useState } from "react";
import { useTranslation } from "react-i18next";

import { UpgradeSheet } from "@/components/UpgradeSheet";
import {
  SettingsChoiceRow,
  SettingsGroup,
  SettingsPage,
  useSettingsAction,
} from "@/features/account/components/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { buildModelPreferences, useModels } from "@/hooks/useModels";
import { planNameKey } from "@/lib/plan";

/**
 * Settings → Model: one choice. Auto picks a fast model for everyday questions
 * and a stronger one when a question needs it; or every message uses the one
 * model picked here. It is the same single choice "use Luna" makes from chat.
 */
export default function ModelsSettingsScreen() {
  const { updateUser } = useAuth();
  const { t } = useTranslation();
  const { models, isPaid, autoEnabled, modelEnabledSet } = useModels();
  const action = useSettingsAction();
  const [upgradeVisible, setUpgradeVisible] = useState(false);

  const [chosenModel] = modelEnabledSet;
  const selected = autoEnabled || !chosenModel ? "auto" : chosenModel;

  const choose = (key: string) => {
    if (key === selected || action.busy !== null) return;
    const preferences =
      key === "auto" ? buildModelPreferences(true, []) : [key];
    void action.run(key, () => updateUser({ enabled_models: preferences }));
  };

  return (
    <>
      <SettingsPage>
        <SettingsGroup>
          <SettingsChoiceRow
            icon="sparkles"
            title={t("settings.model_auto")}
            subtitle={t("settings.model_auto_summary")}
            selected={selected === "auto"}
            busy={action.busy === "auto"}
            disabled={action.busy !== null}
            onPress={() => choose("auto")}
          />
        </SettingsGroup>

        <SettingsGroup label={t("settings.models_list")}>
          {models.map((option) => {
            const locked = !isPaid && option.plan_access === "pro";
            const note = locked
              ? t(planNameKey("plus"))
              : option.healthy === false || !option.available
                ? t("settings.model_degraded")
                : undefined;
            return (
              <SettingsChoiceRow
                key={option.id}
                title={option.label}
                subtitle={option.description || undefined}
                value={note}
                selected={selected === option.id}
                busy={action.busy === option.id}
                disabled={
                  action.busy !== null || (!locked && !option.available)
                }
                onPress={() =>
                  locked ? setUpgradeVisible(true) : choose(option.id)
                }
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

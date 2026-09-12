import { useState } from "react";
import { useTranslation } from "react-i18next";

import { SettingsOverviewRow } from "@/components/settings/SettingsOverview";
import { SettingsPickerSheet } from "@/components/settings/SettingsPickerSheet";
import { useAppearance } from "@/contexts/AppearanceContext";
import { APPEARANCE_OPTIONS } from "@/lib/appearance";

export function AppearanceSettingsRow() {
  const { t } = useTranslation();
  const { preference, setPreference } = useAppearance();
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <SettingsOverviewRow
        icon="contrast-outline"
        title={t("settings.appearance")}
        accessibilityHint={t("settings.appearance_summary")}
        value={t(`settings.appearance_${preference}`)}
        expanded={expanded}
        onPress={() => setExpanded(true)}
      />
      <SettingsPickerSheet
        visible={expanded}
        options={APPEARANCE_OPTIONS.map((option) => ({
          key: option,
          label: t(`settings.appearance_${option}`),
        }))}
        selectedKey={preference}
        onClose={() => setExpanded(false)}
        onSelect={(key) => {
          const option = APPEARANCE_OPTIONS.find((candidate) => candidate === key);
          if (option) void setPreference(option);
        }}
      />
    </>
  );
}

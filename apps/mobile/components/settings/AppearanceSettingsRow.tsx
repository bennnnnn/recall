import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  makeSettingsStyles,
  SettingsInlinePicker,
} from "@/components/settings/settingsUi";
import { useAppearance } from "@/contexts/AppearanceContext";
import { APPEARANCE_OPTIONS } from "@/lib/appearance";
import { useTheme } from "@/lib/theme";

export function AppearanceSettingsRow() {
  const { t } = useTranslation();
  const theme = useTheme();
  const styles = useMemo(() => makeSettingsStyles(theme), [theme]);
  const { preference, setPreference } = useAppearance();
  const [expanded, setExpanded] = useState(false);

  return (
    <SettingsInlinePicker
      icon="contrast-outline"
      title={t("settings.appearance")}
      subtitle={t("settings.appearance_summary")}
      value={t(`settings.appearance_${preference}`)}
      options={APPEARANCE_OPTIONS.map((option) => ({
        key: option,
        label: t(`settings.appearance_${option}`),
      }))}
      selectedKey={preference}
      expanded={expanded}
      onToggle={() => setExpanded((open) => !open)}
      onSelect={(key) => {
        const option = APPEARANCE_OPTIONS.find((candidate) => candidate === key);
        if (option) void setPreference(option);
      }}
      styles={styles}
      theme={theme}
    />
  );
}

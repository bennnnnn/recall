import { useRef, useState } from "react";
import type { View } from "react-native";
import { useTranslation } from "react-i18next";

import { SettingsOverviewRow } from "@/components/settings/SettingsOverview";
import { useAppearance } from "@/contexts/AppearanceContext";
import { APPEARANCE_OPTIONS } from "@/lib/appearance";
import { SelectMenu } from "@/ui/overlay/SelectMenu";

export function AppearanceSettingsRow() {
  const { t } = useTranslation();
  const { preference, setPreference } = useAppearance();
  const [expanded, setExpanded] = useState(false);
  const rowRef = useRef<View>(null);

  return (
    <>
      <SettingsOverviewRow
        ref={rowRef}
        icon="contrast"
        title={t("settings.appearance")}
        accessibilityHint={t("settings.appearance_summary")}
        value={t(`settings.appearance_${preference}`)}
        expanded={expanded}
        onPress={() => setExpanded(true)}
      />
      <SelectMenu
        visible={expanded}
        anchorRef={rowRef}
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

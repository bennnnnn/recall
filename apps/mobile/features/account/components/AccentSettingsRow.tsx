import { useRef, useState } from "react";
import type { View } from "react-native";
import { useTranslation } from "react-i18next";

import { useAccent } from "@/contexts/AppearanceContext";
import { SettingsOverviewRow } from "@/features/account/components/SettingsOverview";
import { ACCENT_OPTIONS, accentSwatch } from "@/lib/accent";
import { useTheme } from "@/lib/theme";
import { SelectMenu } from "@/ui/overlay/SelectMenu";

/** Settings → Accent color: the hue on buttons, links, selection and your bubbles. */
export function AccentSettingsRow() {
  const { t } = useTranslation();
  const theme = useTheme();
  const { accent, setAccent } = useAccent();
  const [expanded, setExpanded] = useState(false);
  const rowRef = useRef<View>(null);

  return (
    <>
      <SettingsOverviewRow
        ref={rowRef}
        icon="palette"
        title={t("settings.accent")}
        accessibilityHint={t("settings.accent_summary")}
        value={t(`settings.accent_${accent}`)}
        expanded={expanded}
        onPress={() => setExpanded(true)}
      />
      <SelectMenu
        visible={expanded}
        anchorRef={rowRef}
        options={ACCENT_OPTIONS.map((option) => ({
          key: option,
          label: t(`settings.accent_${option}`),
          swatch: accentSwatch(option, theme.scheme),
        }))}
        selectedKey={accent}
        onClose={() => setExpanded(false)}
        onSelect={(key) => {
          const option = ACCENT_OPTIONS.find((candidate) => candidate === key);
          if (option) void setAccent(option);
        }}
      />
    </>
  );
}

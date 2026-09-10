import { useMemo, useState } from "react";
import { ScrollView } from "react-native";
import { Redirect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsInlinePicker,
} from "@/components/settings/settingsUi";
import { useAppearance } from "@/contexts/AppearanceContext";
import { useAuth } from "@/contexts/AuthContext";
import { APPEARANCE_OPTIONS } from "@/lib/appearance";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

export default function AppearanceSettingsScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const { preference, setPreference } = useAppearance();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const [expanded, setExpanded] = useState(true);

  if (!token) return <Redirect href="/login" />;

  return (
    <ScrollView
      style={s.scroll}
      contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
    >
      <SettingsGroup styles={s}>
        <SettingsInlinePicker
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
          onSelect={(option) =>
            void setPreference(option as (typeof APPEARANCE_OPTIONS)[number])
          }
          styles={s}
          theme={theme}
        />
      </SettingsGroup>
    </ScrollView>
  );
}

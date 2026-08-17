import { useMemo } from "react";
import { ScrollView, View } from "react-native";
import Constants from "expo-constants";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsLinkRow,
  SettingsValueRow,
} from "@/components/settings/settingsUi";
import { getLegalPrivacyUrl, getLegalTermsUrl } from "@/lib/legalUrls";
import { openAllowedUrl } from "@/lib/linkSchemePolicy";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

export default function AboutScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const appVersion = Constants.expoConfig?.version ?? "1.0.0";

  return (
    <ScrollView
      style={s.scroll}
      contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
    >
      <SettingsGroup styles={s}>
        <SettingsLinkRow
          icon="shield-checkmark-outline"
          title={t("privacy.title")}
          subtitle={t("settings.privacy_summary")}
          onPress={() => void openAllowedUrl(getLegalPrivacyUrl())}
          styles={s}
          theme={theme}
        />
        <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
        <SettingsLinkRow
          icon="document-text-outline"
          title={t("terms.title")}
          subtitle={t("settings.terms_summary")}
          onPress={() => void openAllowedUrl(getLegalTermsUrl())}
          styles={s}
          theme={theme}
        />
      </SettingsGroup>
      <SettingsGroup styles={s}>
        <SettingsValueRow
          icon="phone-portrait-outline"
          title={t("settings.about_version")}
          value={appVersion}
          styles={s}
          theme={theme}
        />
      </SettingsGroup>
    </ScrollView>
  );
}

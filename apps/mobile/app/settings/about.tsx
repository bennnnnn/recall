import { useMemo } from "react";
import { Linking, ScrollView, View } from "react-native";
import Constants from "expo-constants";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { InfoRow, makeSettingsStyles, NavRow } from "@/components/settings/settingsUi";
import { getLegalPrivacyUrl, getLegalTermsUrl } from "@/lib/legalUrls";
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
      contentContainerStyle={[s.content, { paddingBottom: insets.bottom + 24 }]}
    >
      <View style={s.menuStack}>
        <View style={s.footerGroup}>
          <NavRow
            icon="shield-checkmark-outline"
            title={t("privacy.title")}
            onPress={() => void Linking.openURL(getLegalPrivacyUrl())}
            compact
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <NavRow
            icon="document-text-outline"
            title={t("terms.title")}
            onPress={() => void Linking.openURL(getLegalTermsUrl())}
            compact
            styles={s}
            theme={theme}
          />
        </View>
        <View style={s.footerGroup}>
          <InfoRow
            icon="phone-portrait-outline"
            title={t("settings.about_version")}
            value={appVersion}
            compact
            styles={s}
            theme={theme}
          />
        </View>
      </View>
    </ScrollView>
  );
}

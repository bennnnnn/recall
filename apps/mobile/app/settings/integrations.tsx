import { useMemo } from "react";
import { ScrollView, View } from "react-native";
import { Redirect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { StateView } from "@/components/StateView";
import {
  ConnectedAppMark,
  makeSettingsStyles,
  SettingsGroup,
  SettingsLinkRow,
} from "@/components/settings/settingsUi";
import { useSettingsIntegrations } from "@/hooks/useSettingsIntegrations";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";
import { useAuth } from "@/contexts/AuthContext";

export default function ConnectedAppsScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { calendarStatus, gmailStatus, loadError, refresh } = useSettingsIntegrations();

  if (!token) return <Redirect href="/login" />;

  const calendarValue =
    calendarStatus?.connected && calendarStatus.email
      ? calendarStatus.email
      : t("settings.integration_not_connected");
  const gmailValue =
    gmailStatus?.connected && gmailStatus.email
      ? gmailStatus.email
      : t("settings.integration_not_connected");

  return (
    <ScrollView
      style={s.scroll}
      contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
    >
      {loadError ? (
        <StateView
          variant="error"
          compact
          message={t("common.error")}
          onRetry={() => void refresh()}
          retryLabel={t("common.retry")}
        />
      ) : null}
      <SettingsGroup styles={s}>
        <SettingsLinkRow
          leading={<ConnectedAppMark name="logo-google" color={theme.brand.google} />}
          title={t("settings.calendar_title")}
          subtitle={t("settings.calendar_desc")}
          value={calendarValue}
          onPress={() =>
            router.push({ pathname: "/settings/connected-app", params: { id: "calendar" } })
          }
          styles={s}
          theme={theme}
        />
        <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
        <SettingsLinkRow
          leading={<ConnectedAppMark name="mail" color={theme.brand.gmail} />}
          title={t("settings.gmail_title")}
          subtitle={t("settings.gmail_desc")}
          value={gmailValue}
          onPress={() =>
            router.push({ pathname: "/settings/connected-app", params: { id: "gmail" } })
          }
          styles={s}
          theme={theme}
        />
      </SettingsGroup>
    </ScrollView>
  );
}

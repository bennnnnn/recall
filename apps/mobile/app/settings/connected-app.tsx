import { useMemo } from "react";
import { ScrollView, Text, View } from "react-native";
import { Redirect, useLocalSearchParams } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { StateView } from "@/components/StateView";
import {
  ConnectedAppMark,
  makeSettingsStyles,
  SettingsGroup,
  SettingsLinkRow,
  SettingsValueRow,
} from "@/components/settings/settingsUi";
import { useSettingsIntegrations } from "@/hooks/useSettingsIntegrations";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";
import { useAuth } from "@/contexts/AuthContext";

export default function ConnectedAppDetailScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const { id } = useLocalSearchParams<{ id?: string }>();
  const {
    calendarStatus,
    calendarBusy,
    gmailStatus,
    gmailBusy,
    loadError,
    connectCalendar,
    disconnectCalendar,
    syncGmail,
    connectGmail,
    disconnectGmail,
    refresh,
  } = useSettingsIntegrations();

  if (!token) return <Redirect href="/login" />;

  const isGmail = id === "gmail";
  const title = isGmail ? t("settings.gmail_title") : t("settings.calendar_title");
  const subtitle = isGmail ? t("settings.gmail_desc") : t("settings.calendar_desc");
  const mark = isGmail ? (
    <ConnectedAppMark name="mail" color={theme.brand.gmail} />
  ) : (
    <ConnectedAppMark name="logo-google" color={theme.brand.google} />
  );
  const connected = isGmail ? gmailStatus?.connected : calendarStatus?.connected;
  const email = isGmail ? gmailStatus?.email : calendarStatus?.email;
  const busy = isGmail ? gmailBusy : calendarBusy;
  const lastSync =
    isGmail && gmailStatus?.connected && gmailStatus.last_sync_at
      ? t("settings.gmail_last_sync", {
          when: new Date(gmailStatus.last_sync_at).toLocaleString(),
        })
      : null;

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
        <SettingsValueRow
          leading={mark}
          title={title}
          subtitle={subtitle}
          value={
            connected && email
              ? t(isGmail ? "settings.gmail_connected" : "settings.calendar_connected", {
                  email,
                })
              : t("settings.integration_not_connected")
          }
          styles={s}
          theme={theme}
        />
      </SettingsGroup>
      <SettingsGroup styles={s}>
        {lastSync ? (
          <View style={s.menuRow}>
            <View style={s.rowBody}>
              <Text style={s.meta}>{lastSync}</Text>
            </View>
          </View>
        ) : null}
        {lastSync && !busy ? <View style={s.menuSeparator} /> : null}
        {busy ? null : isGmail ? (
          gmailStatus?.connected ? (
            <>
              <SettingsLinkRow
                title={t("settings.gmail_sync")}
                onPress={() => void syncGmail()}
                styles={s}
                theme={theme}
              />
              <View style={s.menuSeparator} />
              <SettingsLinkRow
                title={t("settings.gmail_disconnect")}
                onPress={disconnectGmail}
                danger
                styles={s}
                theme={theme}
              />
            </>
          ) : (
            <SettingsLinkRow
              title={t("settings.gmail_connect")}
              onPress={connectGmail}
              styles={s}
              theme={theme}
            />
          )
        ) : calendarStatus?.connected ? (
          <>
            {calendarStatus.can_write ? null : (
              <>
                <SettingsLinkRow
                  title={t("settings.calendar_upgrade_write")}
                  onPress={() => void connectCalendar(true)}
                  styles={s}
                  theme={theme}
                />
                <View style={s.menuSeparator} />
              </>
            )}
            <SettingsLinkRow
              title={t("settings.calendar_disconnect")}
              onPress={disconnectCalendar}
              danger
              styles={s}
              theme={theme}
            />
          </>
        ) : (
          <SettingsLinkRow
            title={t("settings.calendar_connect")}
            onPress={() => void connectCalendar(false)}
            styles={s}
            theme={theme}
          />
        )}
      </SettingsGroup>
    </ScrollView>
  );
}

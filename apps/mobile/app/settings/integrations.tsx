import { useMemo, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { Redirect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { IntegrationPanel, makeSettingsStyles, SettingsGroup } from "@/components/settings/settingsUi";
import { useSettingsIntegrations } from "@/hooks/useSettingsIntegrations";
import { useTheme } from "@/lib/theme";
import { useAuth } from "@/contexts/AuthContext";

export default function IntegrationsSettingsScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const [calendarExpanded, setCalendarExpanded] = useState(true);
  const [gmailExpanded, setGmailExpanded] = useState(true);
  const {
    calendarStatus,
    calendarBusy,
    gmailStatus,
    gmailBusy,
    connectCalendar,
    disconnectCalendar,
    syncGmail,
    connectGmail,
    disconnectGmail,
  } = useSettingsIntegrations();

  if (!token) return <Redirect href="/login" />;

  return (
    <ScrollView
      style={s.scroll}
      contentContainerStyle={[s.content, { paddingBottom: insets.bottom + 24, gap: 16 }]}
    >
      <SettingsGroup styles={s}>
        <IntegrationPanel
          icon="calendar-outline"
          title={t("settings.calendar_title")}
          showDivider={false}
          summary={
            calendarStatus?.connected && calendarStatus.email
              ? t("settings.calendar_connected", { email: calendarStatus.email })
              : t("settings.integration_not_connected")
          }
          expanded={calendarExpanded}
          busy={calendarBusy}
          onToggle={() => setCalendarExpanded((open) => !open)}
          styles={s}
          theme={theme}
        >
          {calendarStatus?.connected && !calendarStatus.can_write ? (
            <Pressable onPress={() => void connectCalendar(true)} hitSlop={8}>
              <Text style={s.linkBtnText}>{t("settings.calendar_upgrade_write")}</Text>
            </Pressable>
          ) : null}
          <View style={s.integrationActions}>
            {calendarBusy ? null : calendarStatus?.connected ? (
              <Pressable style={s.linkBtn} onPress={disconnectCalendar} hitSlop={8}>
                <Text style={s.linkBtnDanger}>{t("settings.calendar_disconnect")}</Text>
              </Pressable>
            ) : (
              <Pressable style={s.linkBtn} onPress={() => void connectCalendar(false)} hitSlop={8}>
                <Text style={s.linkBtnText}>{t("settings.calendar_connect")}</Text>
              </Pressable>
            )}
          </View>
        </IntegrationPanel>
      </SettingsGroup>

      <SettingsGroup styles={s}>
        <IntegrationPanel
          icon="mail-outline"
          title={t("settings.gmail_title")}
          showDivider={false}
          summary={
            gmailStatus?.connected && gmailStatus.email
              ? t("settings.gmail_connected", { email: gmailStatus.email })
              : t("settings.integration_not_connected")
          }
          expanded={gmailExpanded}
          busy={gmailBusy}
          onToggle={() => setGmailExpanded((open) => !open)}
          styles={s}
          theme={theme}
        >
          {gmailStatus?.connected && gmailStatus.last_sync_at ? (
            <Text style={s.meta}>
              {t("settings.gmail_last_sync", {
                when: new Date(gmailStatus.last_sync_at).toLocaleString(),
              })}
            </Text>
          ) : null}
          <View style={s.integrationActions}>
            {gmailBusy ? null : gmailStatus?.connected ? (
              <View style={s.rowActions}>
                <Pressable style={s.linkBtn} onPress={() => void syncGmail()} hitSlop={8}>
                  <Text style={s.linkBtnText}>{t("settings.gmail_sync")}</Text>
                </Pressable>
                <Pressable style={s.linkBtn} onPress={disconnectGmail} hitSlop={8}>
                  <Text style={s.linkBtnDanger}>{t("settings.gmail_disconnect")}</Text>
                </Pressable>
              </View>
            ) : (
              <Pressable style={s.linkBtn} onPress={connectGmail} hitSlop={8}>
                <Text style={s.linkBtnText}>{t("settings.gmail_connect")}</Text>
              </Pressable>
            )}
          </View>
        </IntegrationPanel>
      </SettingsGroup>
    </ScrollView>
  );
}

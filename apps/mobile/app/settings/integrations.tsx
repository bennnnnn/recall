import { useMemo } from "react";
import { ScrollView, Text, View } from "react-native";
import { Redirect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { StateView } from "@/components/StateView";
import { ConnectedAppCard } from "@/components/settings/ConnectedAppCard";
import {
  ConnectedAppMark,
  makeSettingsStyles,
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
  const {
    calendarStatus, calendarBusy, gmailStatus, gmailBusy, loading, loadError,
    connectCalendar, disconnectCalendar, connectGmail, disconnectGmail, syncGmail, refresh,
  } = useSettingsIntegrations();

  if (!token) return <Redirect href="/login" />;

  const statusLabel = (status: { connected: boolean; email?: string | null } | null) =>
    !status ? undefined : status.connected
      ? status.email || t("settings.integration_connected")
      : t("settings.integration_not_connected");
  const actionsDisabled = loading || calendarBusy || gmailBusy;
  const calendarPending = calendarBusy || (!calendarStatus && !loadError);
  const gmailPending = gmailBusy || (!gmailStatus && !loadError);
  const lastSync = gmailStatus?.connected && gmailStatus.last_sync_at
    ? t("settings.gmail_last_sync", { when: new Date(gmailStatus.last_sync_at).toLocaleString() })
    : undefined;

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
      <ConnectedAppCard
        leading={<ConnectedAppMark name="logo-google" color={theme.brand.google} />}
        title={t("settings.calendar_title")}
        description={!calendarStatus?.connected ? t("settings.calendar_desc") : undefined}
        value={statusLabel(calendarStatus)}
        actionLabel={t(calendarStatus?.connected ? "settings.calendar_disconnect" : "settings.calendar_connect")}
        onAction={calendarStatus?.connected ? disconnectCalendar : () => void connectCalendar(false)}
        busy={calendarPending}
        disabled={actionsDisabled || !calendarStatus}
        styles={s}
        theme={theme}
      >
        {calendarStatus?.connected && !calendarStatus.can_write ? (
          <>
            <View style={s.menuSeparator} />
            <SettingsLinkRow
              title={t("settings.calendar_upgrade_write")}
              onPress={() => void connectCalendar(true)}
              disabled={actionsDisabled}
              styles={s}
              theme={theme}
            />
          </>
        ) : null}
      </ConnectedAppCard>
      <ConnectedAppCard
        leading={<ConnectedAppMark name="mail" color={theme.brand.gmail} />}
        title={t("settings.gmail_title")}
        description={!gmailStatus?.connected ? t("settings.gmail_desc") : undefined}
        value={statusLabel(gmailStatus)}
        actionLabel={t(gmailStatus?.connected ? "settings.gmail_disconnect" : "settings.calendar_connect")}
        onAction={gmailStatus?.connected ? disconnectGmail : connectGmail}
        busy={gmailPending}
        disabled={actionsDisabled || !gmailStatus}
        styles={s}
        theme={theme}
      >
        {gmailStatus?.connected ? (
          <>
            {lastSync ? (
              <View style={s.menuRow}>
                <View style={s.rowBody}>
                  <Text style={s.meta}>{lastSync}</Text>
                </View>
              </View>
            ) : null}
            <View style={s.menuSeparator} />
            <SettingsLinkRow
              title={t("settings.gmail_sync")}
              onPress={() => void syncGmail()}
              disabled={actionsDisabled}
              styles={s}
              theme={theme}
            />
          </>
        ) : null}
      </ConnectedAppCard>
    </ScrollView>
  );
}

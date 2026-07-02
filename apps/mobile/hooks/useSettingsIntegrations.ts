import { useCallback, useEffect, useState } from "react";
import { Alert } from "react-native";
import { useFocusEffect } from "expo-router";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/contexts/AuthContext";
import { api, GoogleCalendarStatus, GoogleGmailStatus } from "@/lib/api";
import { isExpoGo } from "@/lib/expoRuntime";
import { connectGoogleCalendar } from "@/lib/google-calendar";
import { connectGoogleGmail } from "@/lib/google-gmail";
import { gmailSyncMessage } from "@/lib/gmailSyncFeedback";

export function useSettingsIntegrations() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const [calendarStatus, setCalendarStatus] = useState<GoogleCalendarStatus | null>(null);
  const [calendarBusy, setCalendarBusy] = useState(false);
  const [gmailStatus, setGmailStatus] = useState<GoogleGmailStatus | null>(null);
  const [gmailBusy, setGmailBusy] = useState(false);

  const refresh = useCallback(async () => {
    if (!token) return;
    const [calendarR, gmailR] = await Promise.allSettled([
      api.googleCalendarStatus(token),
      api.googleGmailStatus(token),
    ]);
    if (calendarR.status === "fulfilled") setCalendarStatus(calendarR.value);
    if (gmailR.status === "fulfilled") setGmailStatus(gmailR.value);
  }, [token]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useFocusEffect(
    useCallback(() => {
      void refresh();
    }, [refresh]),
  );

  const connectCalendar = async (write = false) => {
    if (!token || calendarBusy) return;
    if (isExpoGo()) {
      Alert.alert(t("settings.calendar_title"), t("settings.calendar_expo_go"));
      return;
    }
    if (calendarStatus?.configured === false) {
      Alert.alert(t("settings.calendar_title"), t("settings.calendar_not_configured"));
      return;
    }
    setCalendarBusy(true);
    try {
      const serverAuthCode = await connectGoogleCalendar({ write });
      const status = await api.connectGoogleCalendar(token, serverAuthCode);
      setCalendarStatus(status);
    } catch (error) {
      const message = error instanceof Error ? error.message : t("settings.calendar_connect_failed");
      if (!message.toLowerCase().includes("cancel")) {
        Alert.alert(t("settings.calendar_title"), message);
      }
    } finally {
      setCalendarBusy(false);
    }
  };

  const disconnectCalendar = () => {
    if (!token || calendarBusy || !calendarStatus?.connected) return;
    Alert.alert(t("settings.calendar_title"), t("settings.calendar_disconnect"), [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("settings.calendar_disconnect"),
        style: "destructive",
        onPress: async () => {
          setCalendarBusy(true);
          try {
            await api.disconnectGoogleCalendar(token);
            setCalendarStatus({ connected: false, configured: calendarStatus?.configured ?? true });
            Alert.alert(t("settings.calendar_title"), t("settings.calendar_disconnected"));
          } catch {
            Alert.alert(t("settings.calendar_title"), t("settings.calendar_connect_failed"));
          } finally {
            setCalendarBusy(false);
          }
        },
      },
    ]);
  };

  const syncGmail = async () => {
    if (!token || gmailBusy || !gmailStatus?.connected) return;
    setGmailBusy(true);
    try {
      const result = await api.syncGoogleGmail(token, { force: true });
      const status = await api.googleGmailStatus(token);
      setGmailStatus(status);
      const message = gmailSyncMessage(result);
      Alert.alert(
        t("settings.gmail_title"),
        t(message.key, "params" in message ? message.params : undefined),
      );
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : t("settings.gmail_sync_failed");
      Alert.alert(t("settings.gmail_title"), message);
    } finally {
      setGmailBusy(false);
    }
  };

  const runGmailConnect = async () => {
    if (!token || gmailBusy) return;
    setGmailBusy(true);
    try {
      const serverAuthCode = await connectGoogleGmail();
      await api.connectGoogleGmail(token, serverAuthCode);
      await api.syncGoogleGmail(token, { force: true });
      const status = await api.googleGmailStatus(token);
      setGmailStatus(status);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : t("settings.gmail_connect_failed");
      if (message !== "Gmail connect cancelled") {
        Alert.alert(t("settings.gmail_title"), message);
      }
    } finally {
      setGmailBusy(false);
    }
  };

  const connectGmail = () => {
    if (!token || gmailBusy) return;
    if (isExpoGo()) {
      Alert.alert(t("settings.gmail_title"), t("settings.gmail_expo_go"));
      return;
    }
    if (gmailStatus?.configured === false) {
      Alert.alert(t("settings.gmail_title"), t("settings.gmail_not_configured"));
      return;
    }
    Alert.alert(t("settings.gmail_title"), t("settings.gmail_connect_confirm"), [
      { text: t("common.cancel"), style: "cancel" },
      { text: t("settings.gmail_connect"), onPress: () => void runGmailConnect() },
    ]);
  };

  const disconnectGmail = () => {
    if (!token || gmailBusy || !gmailStatus?.connected) return;
    Alert.alert(t("settings.gmail_title"), t("settings.gmail_disconnect_confirm"), [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("settings.gmail_disconnect"),
        style: "destructive",
        onPress: async () => {
          setGmailBusy(true);
          try {
            await api.disconnectGoogleGmail(token);
            const status = await api.googleGmailStatus(token);
            setGmailStatus(status);
            Alert.alert(t("settings.gmail_title"), t("settings.gmail_disconnected"));
          } catch {
            Alert.alert(t("settings.gmail_title"), t("settings.gmail_connect_failed"));
          } finally {
            setGmailBusy(false);
          }
        },
      },
    ]);
  };

  const connectedCount =
    (calendarStatus?.connected ? 1 : 0) + (gmailStatus?.connected ? 1 : 0);

  return {
    calendarStatus,
    calendarBusy,
    gmailStatus,
    gmailBusy,
    connectedCount,
    connectCalendar,
    disconnectCalendar,
    syncGmail,
    connectGmail,
    disconnectGmail,
    refresh,
  };
}

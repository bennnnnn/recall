import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Alert } from "react-native";
import { useFocusEffect } from "expo-router";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { api, type GoogleCalendarStatus, type GoogleGmailStatus } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { isExpoGo } from "@/lib/expoRuntime";
import { connectGoogleCalendar } from "@/lib/google-calendar";
import { connectGoogleGmail } from "@/lib/google-gmail";
import { gmailSyncMessage } from "@/lib/gmailSyncFeedback";
import { invalidateSuggestedRemindersCache } from "@/lib/cache/suggestedRemindersCache";
import { invalidateIntegrationStatusCache, patchIntegrationStatusCache } from "@/lib/cache/integrationStatusCache";

type Provider = "calendar" | "gmail";
type Owner = { session: number; signedIn: boolean };
type Snapshot = {
  owner: Owner;
  calendarStatus: GoogleCalendarStatus | null;
  gmailStatus: GoogleGmailStatus | null;
  loading: boolean;
  loadError: boolean;
  operation: Provider | null;
};
type Operation = { owner: Owner; provider: Provider };
const emptySnapshot = (owner: Owner): Snapshot => ({
  owner, calendarStatus: null, gmailStatus: null, loading: owner.signedIn,
  loadError: false, operation: null,
});

export function useSettingsIntegrations() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const session = getSessionGeneration();
  const signedIn = Boolean(token);
  const owner = useMemo(() => ({ session, signedIn }), [session, signedIn]);
  const ownerRef = useRef(owner);
  ownerRef.current = owner;
  const mounted = useRef(true);
  const request = useRef(0);
  const operation = useRef<Operation | null>(null);
  const [state, setState] = useState(() => emptySnapshot(owner));
  const snapshot = useRef(state);
  const publish = useCallback((next: Snapshot) => {
    snapshot.current = next;
    setState(next);
  }, []);

  useEffect(() => {
    mounted.current = true;
    if (snapshot.current.owner !== owner) publish(emptySnapshot(owner));
    return () => {
      mounted.current = false;
      request.current = request.current + 1;
      operation.current = null;
    };
  }, [owner, publish]);

  const current = useCallback(() => mounted.current && owner.signedIn &&
    ownerRef.current === owner && snapshot.current.owner === owner &&
    owner.session === getSessionGeneration(), [owner]);
  const currentOperation = (active: Operation) => current() && operation.current === active;
  const canStart = () => current() && !snapshot.current.loading && !operation.current;
  const begin = (provider: Provider): Operation | null => {
    if (!canStart()) return null;
    const active = { owner, provider };
    operation.current = active;
    request.current++;
    publish({ ...snapshot.current, operation: provider });
    return active;
  };
  const finish = (active: Operation) => {
    if (!currentOperation(active)) return;
    operation.current = null;
    publish({ ...snapshot.current, operation: null });
  };
  const report = (provider: Provider, fallback: string, error?: unknown) => {
    if (!current()) return;
    const message = error instanceof Error ? error.message : t(fallback);
    if (message.toLowerCase().includes("cancel")) return;
    if (feedback) feedback.error(message);
    else Alert.alert(t(provider === "calendar" ? "settings.calendar_title" : "settings.gmail_title"), message);
  };
  const applyCalendar = (status: GoogleCalendarStatus) => {
    publish({ ...snapshot.current, calendarStatus: status });
    patchIntegrationStatusCache({ calendarConnected: status.connected });
  };
  const applyGmail = (status: GoogleGmailStatus) => {
    publish({ ...snapshot.current, gmailStatus: status });
    patchIntegrationStatusCache({ gmailConnected: status.connected });
  };

  const refresh = useCallback(async (opts?: { silent?: boolean }) => {
    if (!token || !current() || (operation.current && !opts?.silent)) return;
    const revision = ++request.current;
    if (!opts?.silent) publish({ ...snapshot.current, loading: true, loadError: false });
    const [calendarR, gmailR] = await Promise.allSettled([
      api.googleCalendarStatus(token), api.googleGmailStatus(token),
    ]);
    if (!current() || revision !== request.current) return;
    publish({
      ...snapshot.current,
      calendarStatus: calendarR.status === "fulfilled" ? calendarR.value : snapshot.current.calendarStatus,
      gmailStatus: gmailR.status === "fulfilled" ? gmailR.value : snapshot.current.gmailStatus,
      loadError: calendarR.status === "rejected" || gmailR.status === "rejected",
      loading: false,
    });
    if (calendarR.status === "fulfilled" || gmailR.status === "fulfilled") {
      patchIntegrationStatusCache({
        calendarConnected: calendarR.status === "fulfilled" ? calendarR.value.connected : undefined,
        gmailConnected: gmailR.status === "fulfilled" ? gmailR.value.connected : undefined,
      });
    }
  }, [token, current, publish]);

  useFocusEffect(useCallback(() => { void refresh(); }, [refresh]));

  const canConnect = (provider: Provider) => {
    if (!canStart()) return false;
    const status = provider === "calendar" ? snapshot.current.calendarStatus : snapshot.current.gmailStatus;
    if (!status) return false;
    const title = t(provider === "calendar" ? "settings.calendar_title" : "settings.gmail_title");
    if (isExpoGo()) {
      Alert.alert(title, t(provider === "calendar" ? "settings.calendar_expo_go" : "settings.gmail_expo_go"));
      return false;
    }
    if (!status.configured) {
      Alert.alert(title, t(provider === "calendar" ? "settings.calendar_not_configured" : "settings.gmail_not_configured"));
      return false;
    }
    return true;
  };

  const connectCalendar = async (write = false) => {
    if (!token || !canConnect("calendar")) return;
    const active = begin("calendar");
    if (!active) return;
    try {
      const code = await connectGoogleCalendar({ write });
      if (!currentOperation(active)) return;
      const status = await api.connectGoogleCalendar(token, code);
      if (currentOperation(active)) applyCalendar(status);
    } catch (error) {
      if (currentOperation(active)) report("calendar", "settings.calendar_connect_failed", error);
    } finally { finish(active); }
  };

  const connectGmail = async () => {
    if (!token || !canConnect("gmail")) return;
    const active = begin("gmail");
    if (!active) return;
    let connected = false;
    try {
      const code = await connectGoogleGmail();
      if (!currentOperation(active)) return;
      const status = await api.connectGoogleGmail(token, code);
      if (!currentOperation(active)) return;
      connected = true;
      applyGmail(status);
      await api.syncGoogleGmail(token, { force: true });
      if (!currentOperation(active)) return;
      const synced = await api.googleGmailStatus(token);
      if (currentOperation(active)) applyGmail(synced);
    } catch (error) {
      if (currentOperation(active)) report("gmail",
        connected ? "settings.gmail_sync_failed" : "settings.gmail_connect_failed", error);
    } finally { finish(active); }
  };

  const syncGmail = async () => {
    if (!token || !snapshot.current.gmailStatus?.connected) return;
    const active = begin("gmail");
    if (!active) return;
    try {
      const result = await api.syncGoogleGmail(token, { force: true });
      if (!currentOperation(active)) return;
      const status = await api.googleGmailStatus(token);
      if (!currentOperation(active)) return;
      applyGmail(status);
      const message = gmailSyncMessage(result);
      feedback?.success(t(message.key, "params" in message ? message.params : undefined));
    } catch (error) {
      if (currentOperation(active)) report("gmail", "settings.gmail_sync_failed", error);
    } finally { finish(active); }
  };

  const disconnect = (provider: Provider) => {
    const status = () => provider === "calendar" ? snapshot.current.calendarStatus : snapshot.current.gmailStatus;
    if (!token || !canStart() || !status()?.connected) return;
    Alert.alert(
      t(provider === "calendar" ? "settings.calendar_title" : "settings.gmail_title"),
      t(provider === "calendar" ? "settings.calendar_disconnect_confirm" : "settings.gmail_disconnect_confirm"),
      [
        { text: t("common.cancel"), style: "cancel" },
        {
          text: t(provider === "calendar" ? "settings.calendar_disconnect" : "settings.gmail_disconnect"),
          style: "destructive",
          onPress: async () => {
            if (!status()?.connected) return;
            const active = begin(provider);
            if (!active) return;
            try {
              if (provider === "calendar") await api.disconnectGoogleCalendar(token);
              else await api.disconnectGoogleGmail(token);
              if (!currentOperation(active)) return;
              invalidateSuggestedRemindersCache();
              invalidateIntegrationStatusCache();
              // Google can revoke the sibling service too. Refresh its state
              // before offering actions against a possibly revoked connection.
              const previous = snapshot.current;
              publish({ ...previous,
                calendarStatus: provider === "calendar"
                  ? { configured: previous.calendarStatus?.configured ?? true, connected: false } : null,
                gmailStatus: provider === "gmail"
                  ? { configured: previous.gmailStatus?.configured ?? true, connected: false } : null,
              });
              await refresh({ silent: true });
            } catch {
              if (currentOperation(active)) report(provider,
                provider === "calendar" ? "settings.calendar_connect_failed" : "settings.gmail_connect_failed");
            } finally { finish(active); }
          },
        },
      ],
    );
  };

  const visible = state.owner === owner ? state : emptySnapshot(owner);
  return {
    loading: visible.loading,
    loadError: visible.loadError,
    calendarStatus: visible.calendarStatus,
    calendarBusy: visible.operation === "calendar",
    gmailStatus: visible.gmailStatus,
    gmailBusy: visible.operation === "gmail",
    connectedCount: (visible.calendarStatus?.connected ? 1 : 0) + (visible.gmailStatus?.connected ? 1 : 0),
    connectCalendar,
    disconnectCalendar: () => disconnect("calendar"),
    syncGmail,
    connectGmail,
    disconnectGmail: () => disconnect("gmail"),
    refresh,
  };
}

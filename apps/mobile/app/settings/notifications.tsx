import { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { Alert, ScrollView, View } from "react-native";
import { Redirect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsInlinePicker,
  SettingsSwitchRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { getSessionGeneration } from "@/lib/auth";
import {
  DEFAULT_REMINDER_LEAD_MINUTES,
  getReminderLeadMinutes,
  REMINDER_LEAD_OPTIONS,
} from "@/lib/reminderPrefs";
import { normalizeReminderLeadMinutes } from "@/lib/todos/reminderTiming";
import {
  ensureNotificationPermission,
  registerRemotePushToken,
  unregisterRemotePushToken,
} from "@/lib/pushNotifications";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

let pending: { session: number; action: string } | null = null;
const listeners = new Set<() => void>();
function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
function notify() { listeners.forEach((listener) => listener()); }

export default function NotificationsSettingsScreen() {
  const view = useAccountViewOwner();
  return <NotificationsSettingsContent key={view.key} isCurrentView={view.isCurrent} />;
}

function NotificationsSettingsContent({ isCurrentView }: { isCurrentView: () => boolean }) {
  const { token, user, updateUser } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const [leadOpen, setLeadOpen] = useState(false);
  const [reminderLeadMinutes, setReminderLeadMinutesState] = useState(
    DEFAULT_REMINDER_LEAD_MINUTES,
  );
  const session = getSessionGeneration();
  const busyAction = useSyncExternalStore(subscribe, () => pending?.session === session ? pending.action : null);
  const sameAccount = useCallback(() => Boolean(token) && session === getSessionGeneration(), [token, session]);
  const isCurrent = useCallback(() => isCurrentView() && sameAccount(), [isCurrentView, sameAccount]);
  const begin = useCallback((action: string) => {
    if (!token || !isCurrent() || pending?.session === session) return null;
    const request = { session, action };
    pending = request;
    notify();
    return request;
  }, [token, isCurrent, session]);
  const finish = useCallback((request: NonNullable<typeof pending>) => {
    if (pending === request) { pending = null; notify(); }
  }, []);
  const feedback = useActionFeedbackOptional();

  const reportError = useCallback((key: string) => {
    if (!isCurrent()) return;
    if (feedback) feedback.error(t(key));
    else Alert.alert(t("common.error"), t(key));
  }, [isCurrent, feedback, t]);

  useEffect(() => {
    if (!isCurrent()) return;
    if (user?.reminder_lead_minutes != null) {
      setReminderLeadMinutesState(normalizeReminderLeadMinutes(user.reminder_lead_minutes));
      return;
    }
    let active = true;
    void getReminderLeadMinutes().then((minutes) => {
      if (active && isCurrent()) setReminderLeadMinutesState(minutes);
    }).catch(() => { if (active) reportError("common.error"); });
    return () => { active = false; };
  }, [isCurrent, reportError, user?.reminder_lead_minutes]);

  const saveReminderLead = useCallback(async (minutes: number) => {
    const request = begin("lead");
    if (!request) return;
    const previous = reminderLeadMinutes;
    const normalized = normalizeReminderLeadMinutes(minutes);
    try {
      setReminderLeadMinutesState(normalized);
      // Profile/bootstrap and TodosProvider own preference persistence and scheduling.
      await updateUser({ reminder_lead_minutes: normalized });
    } catch {
      if (isCurrent()) setReminderLeadMinutesState(previous);
      reportError("common.error");
    } finally { finish(request); }
  }, [begin, reminderLeadMinutes, updateUser, isCurrent, reportError, finish]);

  const togglePush = useCallback(async (enabled: boolean) => {
    if (!token) return;
    const request = begin("push");
    if (!request) return;
    try {
      if (!enabled) {
        await updateUser({ push_notifications_enabled: false });
        if (sameAccount()) await unregisterRemotePushToken(token);
        return;
      }
      const granted = await ensureNotificationPermission(token);
      if (!sameAccount()) return;
      if (!granted) {
        if (isCurrent()) Alert.alert(t("settings.push_blocked_title"), t("settings.push_blocked_message"));
        return;
      }
      await registerRemotePushToken(token, true);
      if (sameAccount()) await updateUser({ push_notifications_enabled: true });
    } catch { reportError("settings.push_register_failed"); }
    finally { finish(request); }
  }, [token, begin, updateUser, sameAccount, isCurrent, t, reportError, finish]);

  const toggleEmailReminders = useCallback(async (enabled: boolean) => {
    const request = begin("email");
    if (!request) return;
    try { await updateUser({ email_reminders_enabled: enabled }); }
    catch { reportError("common.error"); }
    finally { finish(request); }
  }, [begin, updateUser, reportError, finish]);

  if (!token) return <Redirect href="/login" />;

  return (
    <>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
      >
        <SettingsGroup label={t("settings.notifications")} styles={s}>
          <SettingsSwitchRow
            icon="notifications-outline"
            title={t("settings.push_notifications")}
            subtitle={t("settings.push_notifications_desc")}
            value={user?.push_notifications_enabled ?? true}
            disabled={busyAction !== null}
            busy={busyAction === "push"}
            onValueChange={togglePush}
            styles={s}
            theme={theme}
          />
          <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
          <SettingsSwitchRow
            icon="mail-outline"
            title={t("settings.email_reminders")}
            subtitle={t("settings.email_reminders_summary")}
            value={user?.email_reminders_enabled ?? false}
            disabled={busyAction !== null}
            busy={busyAction === "email"}
            onValueChange={(v) => void toggleEmailReminders(v)}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>

        <SettingsGroup label={t("settings.reminders")} styles={s}>
          <SettingsInlinePicker
            icon="alarm-outline"
            title={t("settings.reminder_lead")}
            subtitle={t("settings.reminder_lead_desc")}
            value={t("settings.reminder_lead_value", { count: reminderLeadMinutes })}
            options={REMINDER_LEAD_OPTIONS.map((minutes) => ({
              key: String(minutes),
              label: t("settings.reminder_lead_value", { count: minutes }),
            }))}
            selectedKey={String(reminderLeadMinutes)}
            expanded={leadOpen}
            disabled={busyAction !== null}
            busy={busyAction === "lead"}
            onToggle={() => { if (isCurrent()) setLeadOpen((open) => !open); }}
            onSelect={(key) => void saveReminderLead(Number(key))}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>
      </ScrollView>
    </>
  );
}

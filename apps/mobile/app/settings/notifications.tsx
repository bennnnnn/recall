import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
import { useTodos } from "@/contexts/TodosContext";
import {
  DEFAULT_REMINDER_LEAD_MINUTES,
  getReminderLeadMinutes,
  REMINDER_LEAD_OPTIONS,
  setReminderLeadMinutes,
  syncReminderLeadFromServer,
} from "@/lib/reminderPrefs";
import { normalizeReminderLeadMinutes } from "@/lib/todos/reminderTiming";
import { syncTodoReminders } from "@/lib/todos/todoReminders";
import {
  ensureNotificationPermission,
  registerRemotePushToken,
  unregisterRemotePushToken,
} from "@/lib/pushNotifications";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

export default function NotificationsSettingsScreen() {
  const { token, user, updateUser } = useAuth();
  const { todos } = useTodos();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const [leadOpen, setLeadOpen] = useState(false);
  const [reminderLeadMinutes, setReminderLeadMinutesState] = useState(
    DEFAULT_REMINDER_LEAD_MINUTES,
  );
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const busyRef = useRef(false);
  const feedback = useActionFeedbackOptional();

  useEffect(() => {
    if (user?.reminder_lead_minutes != null) {
      const minutes = normalizeReminderLeadMinutes(user.reminder_lead_minutes);
      setReminderLeadMinutesState(minutes);
      void syncReminderLeadFromServer(minutes);
      return;
    }
    void getReminderLeadMinutes().then(setReminderLeadMinutesState);
  }, [user?.reminder_lead_minutes]);

  const saveReminderLead = useCallback(
    async (minutes: number) => {
      if (busyRef.current) return;
      busyRef.current = true;
      setBusyAction("lead");
      const previous = reminderLeadMinutes;
      const normalized = normalizeReminderLeadMinutes(minutes);
      try {
        setReminderLeadMinutesState(normalized);
        await setReminderLeadMinutes(normalized);
        await updateUser({ reminder_lead_minutes: normalized });
        await syncTodoReminders(todos);
      } catch {
        setReminderLeadMinutesState(previous);
        await setReminderLeadMinutes(previous).catch(() => {});
        if (feedback) feedback.error(t("common.error"));
        else Alert.alert(t("todos.error"), t("common.error"));
      } finally {
        busyRef.current = false;
        setBusyAction(null);
      }
    },
    [feedback, reminderLeadMinutes, t, todos, updateUser],
  );

  const togglePush = useCallback(
    async (v: boolean) => {
      if (!token || busyRef.current) return;
      busyRef.current = true;
      setBusyAction("push");
      try {
        if (!v) {
        // Disabling: flip the server flag AND unregister the Expo push token
        // from the backend. Without the unregister, the backend keeps a live
        // push token for a user who opted out and keeps sending them
        // notifications until the token is overwritten or expires.
          await updateUser({ push_notifications_enabled: false });
          await unregisterRemotePushToken(token);
          return;
        }
      // Enabling: the server flag alone does nothing on-device — we must also
      // request OS notification permission and register the Expo push token.
      // Without this the toggle silently lied "on" but no token was ever sent.
        const granted = await ensureNotificationPermission(token);
        if (!granted) {
          Alert.alert(
            t("settings.push_blocked_title"),
            t("settings.push_blocked_message"),
          );
          return; // leave the toggle off — permission was denied
        }
        await registerRemotePushToken(token, true);
        await updateUser({ push_notifications_enabled: true });
      } catch {
        if (feedback) feedback.error(t("settings.push_register_failed"));
        else Alert.alert(t("common.error"), t("settings.push_register_failed"));
      } finally {
        busyRef.current = false;
        setBusyAction(null);
      }
    },
    [feedback, t, token, updateUser],
  );

  const toggleEmailReminders = useCallback(
    async (v: boolean) => {
      if (busyRef.current) return;
      busyRef.current = true;
      setBusyAction("email");
      try {
        await updateUser({ email_reminders_enabled: v });
      } catch {
        if (feedback) feedback.error(t("common.error"));
        else Alert.alert(t("common.error"), t("common.error"));
      } finally {
        busyRef.current = false;
        setBusyAction(null);
      }
    },
    [feedback, t, updateUser],
  );

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
            onToggle={() => setLeadOpen((open) => !open)}
            onSelect={(key) => void saveReminderLead(Number(key))}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>
      </ScrollView>
    </>
  );
}

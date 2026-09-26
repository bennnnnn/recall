import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { ScrollView, View } from "react-native";
import { Redirect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsInlinePicker,
  SettingsLinkRow,
  SettingsSwitchRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { usePushNotificationToggle } from "@/hooks/usePushNotificationToggle";
import { getSessionGeneration } from "@/lib/auth";
import { minutesFromTime, timeFromMinutes } from "@/lib/datetime/clockDial";
import { formatMinuteOfDay } from "@/lib/datetime/format";
import {
  DEFAULT_REMINDER_LEAD_MINUTES,
  getReminderLeadMinutes,
  REMINDER_LEAD_OPTIONS,
} from "@/features/todos/model/reminderPrefs";
import { normalizeReminderLeadMinutes } from "@/features/todos/model/reminderTiming";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";
import { alertDialog } from "@/ui/overlay/dialogs";
import { TimePickerDialog } from "@/ui/pickers/TimePickerDialog";

const DEFAULT_QUIET_START = 1320;
const DEFAULT_QUIET_END = 420;

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
  const [pickingQuiet, setPickingQuiet] = useState<"start" | "end" | null>(null);
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
    else void alertDialog({ title: t("common.error"), message: t(key) });
  }, [isCurrent, feedback, t]);

  const acquirePushMutation = useCallback(() => {
    const request = begin("push");
    return request ? () => finish(request) : null;
  }, [begin, finish]);
  const updatePushPreference = useCallback(
    (enabled: boolean) => updateUser({ push_notifications_enabled: enabled }),
    [updateUser],
  );
  const reportPushDenied = useCallback(() => {
    void alertDialog({
      title: t("settings.push_blocked_title"),
      message: t("settings.push_blocked_message"),
    });
  }, [t]);
  const reportPushError = useCallback(
    () => reportError("settings.push_register_failed"),
    [reportError],
  );
  const pushToggle = usePushNotificationToggle({
    token,
    serverEnabled: user?.push_notifications_enabled ?? true,
    isCurrentView: isCurrent,
    updatePreference: updatePushPreference,
    acquireMutation: acquirePushMutation,
    onPermissionDenied: reportPushDenied,
    onError: reportPushError,
  });

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

  const quietEnabled = user?.quiet_hours_enabled === true;
  const quietStart = user?.quiet_hours_start_minute ?? DEFAULT_QUIET_START;
  const quietEnd = user?.quiet_hours_end_minute ?? DEFAULT_QUIET_END;

  const saveReminderLead = useCallback(async (minutes: number) => {
    const request = begin("lead");
    if (!request) return;
    const previous = reminderLeadMinutes;
    const normalized = normalizeReminderLeadMinutes(minutes);
    try {
      setReminderLeadMinutesState(normalized);
      await updateUser({ reminder_lead_minutes: normalized });
    } catch {
      if (isCurrent()) setReminderLeadMinutesState(previous);
      reportError("common.error");
    } finally { finish(request); }
  }, [begin, reminderLeadMinutes, updateUser, isCurrent, reportError, finish]);

  const toggleEmailReminders = useCallback(async (enabled: boolean) => {
    const request = begin("email");
    if (!request) return;
    try { await updateUser({ email_reminders_enabled: enabled }); }
    catch { reportError("common.error"); }
    finally { finish(request); }
  }, [begin, updateUser, reportError, finish]);

  const toggleQuietHours = useCallback(async (enabled: boolean) => {
    const request = begin("quiet");
    if (!request) return;
    try {
      await updateUser({ quiet_hours_enabled: enabled });
    } catch {
      reportError("common.error");
    } finally {
      finish(request);
    }
  }, [begin, updateUser, reportError, finish]);

  // The dialog keeps its title and time through the closing fade.
  const quietShown = useRef<"start" | "end">("start");
  const openQuietPicker = useCallback(
    (which: "start" | "end") => {
      if (!isCurrent()) return;
      quietShown.current = which;
      setPickingQuiet(which);
    },
    [isCurrent],
  );

  const saveQuietMinutes = useCallback(
    async (which: "start" | "end", minutes: number) => {
      const request = begin(`quiet-${which}`);
      if (!request) return;
      try {
        if (which === "start") {
          await updateUser({ quiet_hours_start_minute: minutes });
        } else {
          await updateUser({ quiet_hours_end_minute: minutes });
        }
      } catch {
        reportError("common.error");
      } finally {
        finish(request);
      }
    },
    [begin, updateUser, reportError, finish],
  );

  if (!token) return <Redirect href="/login" />;

  return (
    <>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
      >
        <SettingsGroup styles={s}>
          <SettingsSwitchRow
            title={t("settings.push_notifications")}
            value={pushToggle.value}
            disabled={busyAction !== null}
            onValueChange={pushToggle.toggle}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsSwitchRow
            title={t("settings.email_reminders")}
            value={user?.email_reminders_enabled ?? false}
            disabled={busyAction !== null}
            busy={busyAction === "email"}
            onValueChange={(v) => void toggleEmailReminders(v)}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>

        <SettingsGroup styles={s}>
          <SettingsSwitchRow
            title={t("settings.quiet_hours")}
            value={quietEnabled}
            disabled={busyAction !== null}
            busy={busyAction === "quiet"}
            onValueChange={(v) => void toggleQuietHours(v)}
            styles={s}
            theme={theme}
          />
          {quietEnabled ? (
            <>
              <View style={s.menuSeparator} />
              <SettingsLinkRow
                title={t("settings.quiet_hours_start")}
                value={formatMinuteOfDay(quietStart)}
                disabled={busyAction !== null}
                busy={busyAction === "quiet-start"}
                onPress={() => openQuietPicker("start")}
                styles={s}
                theme={theme}
              />
              <View style={s.menuSeparator} />
              <SettingsLinkRow
                title={t("settings.quiet_hours_end")}
                value={formatMinuteOfDay(quietEnd)}
                disabled={busyAction !== null}
                busy={busyAction === "quiet-end"}
                onPress={() => openQuietPicker("end")}
                styles={s}
                theme={theme}
              />
            </>
          ) : null}
        </SettingsGroup>

        <SettingsGroup styles={s}>
          <SettingsInlinePicker
            title={t("settings.reminder_lead")}
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

      <TimePickerDialog
        visible={pickingQuiet !== null && quietEnabled}
        title={t(
          quietShown.current === "end"
            ? "settings.quiet_hours_end"
            : "settings.quiet_hours_start",
        )}
        value={timeFromMinutes(quietShown.current === "end" ? quietEnd : quietStart)}
        onCancel={() => setPickingQuiet(null)}
        onConfirm={(time) => {
          const which = pickingQuiet;
          setPickingQuiet(null);
          if (which) void saveQuietMinutes(which, minutesFromTime(time));
        }}
      />
    </>
  );
}

import { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { Alert, Platform, ScrollView, StyleSheet, View } from "react-native";
import DateTimePicker, {
  type DateTimePickerEvent,
} from "@react-native-community/datetimepicker";
import { Redirect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { SheetFormHeader } from "@/components/SheetFormHeader";
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
import {
  DEFAULT_REMINDER_LEAD_MINUTES,
  getReminderLeadMinutes,
  REMINDER_LEAD_OPTIONS,
} from "@/lib/reminderPrefs";
import { normalizeReminderLeadMinutes } from "@/lib/todos/reminderTiming";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

const DEFAULT_QUIET_START = 1320;
const DEFAULT_QUIET_END = 420;

let pending: { session: number; action: string } | null = null;
const listeners = new Set<() => void>();
function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
function notify() { listeners.forEach((listener) => listener()); }

function dateFromMinute(minutes: number): Date {
  const date = new Date();
  date.setHours(Math.floor(minutes / 60), minutes % 60, 0, 0);
  return date;
}

function minuteFromDate(date: Date): number {
  return date.getHours() * 60 + date.getMinutes();
}

function formatClock(minutes: number): string {
  return dateFromMinute(minutes).toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
}

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
  // iOS spins continuously, so the sheet edits a draft and only saves on Done
  // — otherwise every spinner tick is its own profile write.
  const [quietDraft, setQuietDraft] = useState<Date | null>(null);
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

  const acquirePushMutation = useCallback(() => {
    const request = begin("push");
    return request ? () => finish(request) : null;
  }, [begin, finish]);
  const updatePushPreference = useCallback(
    (enabled: boolean) => updateUser({ push_notifications_enabled: enabled }),
    [updateUser],
  );
  const reportPushDenied = useCallback(() => {
    Alert.alert(t("settings.push_blocked_title"), t("settings.push_blocked_message"));
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

  const openQuietPicker = useCallback(
    (which: "start" | "end") => {
      if (!isCurrent()) return;
      setQuietDraft(dateFromMinute(which === "start" ? quietStart : quietEnd));
      setPickingQuiet(which);
    },
    [isCurrent, quietStart, quietEnd],
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
        if (isCurrent()) setPickingQuiet(null);
      } catch {
        reportError("common.error");
      } finally {
        finish(request);
      }
    },
    [begin, updateUser, isCurrent, reportError, finish],
  );

  // Android shows a native dialog; a completed pick commits immediately.
  const onQuietAndroidChange = useCallback(
    (event: DateTimePickerEvent, date?: Date) => {
      const which = pickingQuiet;
      setPickingQuiet(null);
      if (event.type === "dismissed" || !date || !which) return;
      void saveQuietMinutes(which, minuteFromDate(date));
    },
    [pickingQuiet, saveQuietMinutes],
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
            title={t("settings.push_notifications")}
            subtitle={t("settings.push_notifications_desc")}
            value={pushToggle.value}
            disabled={busyAction !== null}
            onValueChange={pushToggle.toggle}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsSwitchRow
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

        <SettingsGroup label={t("settings.quiet_hours")} styles={s}>
          <SettingsSwitchRow
            title={t("settings.quiet_hours")}
            subtitle={t("settings.quiet_hours_desc")}
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
                value={formatClock(quietStart)}
                onPress={() => openQuietPicker("start")}
                styles={s}
                theme={theme}
              />
              <View style={s.menuSeparator} />
              <SettingsLinkRow
                title={t("settings.quiet_hours_end")}
                value={formatClock(quietEnd)}
                onPress={() => openQuietPicker("end")}
                styles={s}
                theme={theme}
              />
            </>
          ) : null}
        </SettingsGroup>

        {pickingQuiet && quietEnabled && Platform.OS === "android" ? (
          <DateTimePicker
            mode="time"
            value={quietDraft ?? dateFromMinute(pickingQuiet === "start" ? quietStart : quietEnd)}
            onChange={onQuietAndroidChange}
            display="default"
          />
        ) : null}

        <SettingsGroup label={t("settings.reminders")} styles={s}>
          <SettingsInlinePicker
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

      <AppSheet
        visible={pickingQuiet !== null && quietEnabled && Platform.OS === "ios"}
        onClose={() => setPickingQuiet(null)}
        variant="bottom"
        withHandle={false}
        contentContainerStyle={localStyles.quietSheet}
      >
        <SheetFormHeader
          title={t(pickingQuiet === "end" ? "settings.quiet_hours_end" : "settings.quiet_hours_start")}
          onCancel={() => setPickingQuiet(null)}
          onSave={() => {
            if (pickingQuiet && quietDraft) {
              void saveQuietMinutes(pickingQuiet, minuteFromDate(quietDraft));
            }
          }}
          cancelLabel={t("common.cancel")}
          saveLabel={t("common.done")}
          saving={pickingQuiet !== null && busyAction === `quiet-${pickingQuiet}`}
        />
        <View style={localStyles.quietPickerWrap}>
          <DateTimePicker
            mode="time"
            value={quietDraft ?? new Date()}
            onChange={(_event, date) => {
              if (date) setQuietDraft(date);
            }}
            display="spinner"
          />
        </View>
      </AppSheet>
    </>
  );
}

const localStyles = StyleSheet.create({
  quietSheet: { paddingHorizontal: 0, paddingTop: 0 },
  quietPickerWrap: { alignItems: "center", paddingVertical: Space.sm },
});

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { useTranslation } from "react-i18next";

import {
  SettingsGroup,
  SettingsLinkRow,
  SettingsMenuRow,
  SettingsPage,
  SettingsSwitchRow,
  useSettingSave,
} from "@/features/account/components/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { usePushNotificationToggle } from "@/features/account/hooks/usePushNotificationToggle";
import { getSessionGeneration } from "@/lib/auth";
import { minutesFromTime, timeFromMinutes } from "@/lib/datetime/clockDial";
import { formatMinuteOfDay } from "@/lib/datetime/format";
import {
  DEFAULT_REMINDER_LEAD_MINUTES,
  normalizeReminderLeadMinutes,
  REMINDER_LEAD_OPTIONS,
} from "@/features/todos/model/reminderTiming";
import { type User } from "@/lib/api";
import { createListenerSet } from "@/lib/listenerSet";
import { alertDialog } from "@/ui/overlay/dialogs";
import { TimePickerDialog } from "@/ui/pickers/TimePickerDialog";

const DEFAULT_QUIET_START = 1320;
const DEFAULT_QUIET_END = 420;

/** Each push kind's switch, shown under the master switch while it is on. */
const PUSH_KINDS = [
  { field: "push_reminders_enabled", title: "settings.push_reminders" },
] as const satisfies readonly { field: keyof User; title: string }[];

let pending: { session: number; action: string } | null = null;
const listeners = createListenerSet();

export default function NotificationsSettingsScreen() {
  const view = useAccountViewOwner();
  return <NotificationsSettingsContent key={view.key} isCurrentView={view.isCurrent} />;
}

function NotificationsSettingsContent({ isCurrentView }: { isCurrentView: () => boolean }) {
  const { token, user, updateUser } = useAuth();
  const { t } = useTranslation();
  const [reminderLeadMinutes, setReminderLeadMinutesState] = useState(
    DEFAULT_REMINDER_LEAD_MINUTES,
  );
  const [pickingQuiet, setPickingQuiet] = useState<"start" | "end" | null>(null);
  const session = getSessionGeneration();
  const busyAction = useSyncExternalStore(listeners.subscribe, () => pending?.session === session ? pending.action : null);
  const sameAccount = useCallback(() => Boolean(token) && session === getSessionGeneration(), [token, session]);
  const isCurrent = useCallback(() => isCurrentView() && sameAccount(), [isCurrentView, sameAccount]);
  const begin = useCallback((action: string) => {
    if (!token || !isCurrent() || pending?.session === session) return null;
    const request = { session, action };
    pending = request;
    listeners.emit();
    return request;
  }, [token, isCurrent, session]);
  const finish = useCallback((request: NonNullable<typeof pending>) => {
    if (pending === request) { pending = null; listeners.emit(); }
  }, []);
  const feedback = useActionFeedbackOptional();
  // A switch saves at once and in order; a tap on a page another account replaced does nothing.
  const save = useSettingSave();
  const saveIfCurrent = useCallback((patch: Partial<User>) => {
    if (isCurrent()) save(patch);
  }, [isCurrent, save]);

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

  // The lead time is the server's (users.reminder_lead_minutes): it works out each reminder's time.
  useEffect(() => {
    if (isCurrent() && user?.reminder_lead_minutes != null) {
      setReminderLeadMinutesState(normalizeReminderLeadMinutes(user.reminder_lead_minutes));
    }
  }, [isCurrent, user?.reminder_lead_minutes]);

  // Quiet hours and email reminders start on for a new account (the owner's call, 2026-11-11).
  const quietEnabled = user?.quiet_hours_enabled !== false;
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


  // The dialog keeps its title and time through the closing fade.
  const [quietShown, setQuietShown] = useState<"start" | "end">("start");
  const openQuietPicker = useCallback(
    (which: "start" | "end") => {
      if (!isCurrent()) return;
      setQuietShown(which);
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

  return (
    <>
      <SettingsPage>
        <SettingsGroup label={t("settings.push_group")}>
          <SettingsSwitchRow
            title={t("settings.push_notifications")}
            value={pushToggle.value}
            // Its permission flow waits for the time rows' saves: held, never a tap that does nothing.
            disabled={busyAction !== null}
            onValueChange={pushToggle.toggle}
          />
          {pushToggle.value
            ? PUSH_KINDS.map((kind) => (
                <SettingsSwitchRow
                  key={kind.field}
                  title={t(kind.title)}
                  value={user?.[kind.field] ?? true}
                  onValueChange={(v) => saveIfCurrent({ [kind.field]: v })}
                />
              ))
            : null}
        </SettingsGroup>

        <SettingsGroup label={t("settings.reminders_group")}>
          <SettingsMenuRow
            title={t("settings.reminder_lead")}
            value={t("settings.reminder_lead_value", { count: reminderLeadMinutes })}
            options={REMINDER_LEAD_OPTIONS.map((minutes) => ({
              key: String(minutes),
              label: t("settings.reminder_lead_value", { count: minutes }),
            }))}
            selectedKey={String(reminderLeadMinutes)}
            disabled={busyAction !== null}
            busy={busyAction === "lead"}
            onSelect={(key) => void saveReminderLead(Number(key))}
          />
          {user?.email_reminders_available === false ? null : (
            <SettingsSwitchRow
              title={t("settings.email_reminders")}
              value={user?.email_reminders_enabled !== false}
              onValueChange={(v) => saveIfCurrent({ email_reminders_enabled: v })}
            />
          )}
        </SettingsGroup>

        <SettingsGroup>
          <SettingsSwitchRow
            title={t("settings.quiet_hours")}
            value={quietEnabled}
            onValueChange={(v) => saveIfCurrent({ quiet_hours_enabled: v })}
          />
          {quietEnabled ? (
            <>
              <SettingsLinkRow
                title={t("settings.quiet_hours_start")}
                value={formatMinuteOfDay(quietStart)}
                disabled={busyAction !== null}
                busy={busyAction === "quiet-start"}
                onPress={() => openQuietPicker("start")}
              />
              <SettingsLinkRow
                title={t("settings.quiet_hours_end")}
                value={formatMinuteOfDay(quietEnd)}
                disabled={busyAction !== null}
                busy={busyAction === "quiet-end"}
                onPress={() => openQuietPicker("end")}
              />
            </>
          ) : null}
        </SettingsGroup>
      </SettingsPage>

      <TimePickerDialog
        visible={pickingQuiet !== null && quietEnabled}
        title={t(
          quietShown === "end"
            ? "settings.quiet_hours_end"
            : "settings.quiet_hours_start",
        )}
        value={timeFromMinutes(quietShown === "end" ? quietEnd : quietStart)}
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

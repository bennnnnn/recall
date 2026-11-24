/**
 * The plans page promises a reminder a day before a free trial ends: this keeps it. Started
 * as the trial is bought, it is a notification on this phone for that day, saying what the
 * plan then costs and where to cancel. One trial at a time, so a new one replaces it.
 */
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

import { AndroidNotificationChannel, notificationSound } from "@/features/notifications/model/notificationChannels";
import { ensureNotificationPermission } from "@/features/notifications/model/pushNotifications";
import i18n from "@/lib/i18n";
import { reportFailure } from "@/lib/sentry";

const TRIAL_REMINDER_ID = "recall-trial-ends";
const DAY_MS = 24 * 60 * 60_000;

/**
 * Whether the page may promise the reminder: notifications are on, or the phone can still
 * ask. Turned off in Settings, nothing could arrive, so the page says nothing.
 */
export async function canRemindTrialEnd(): Promise<boolean> {
  try {
    const permission = await Notifications.getPermissionsAsync();
    return permission.status === "granted" || permission.canAskAgain;
  } catch (error) {
    reportFailure("trial_reminder", error);
    return false;
  }
}

/**
 * Sets the reminder for a day before `trialEnds`, asking for notifications first if the
 * phone has not been asked (the purchase is the user's own step). Resolves whether it is
 * set; never rejects, so a purchase never fails on it.
 */
export async function remindBeforeTrialEnds(trialEnds: Date, price: string, now: Date = new Date()): Promise<boolean> {
  const at = new Date(trialEnds.getTime() - DAY_MS);
  if (at.getTime() <= now.getTime()) return false;
  try {
    if (!(await ensureNotificationPermission())) return false;
    await Notifications.cancelScheduledNotificationAsync(TRIAL_REMINDER_ID);
    await Notifications.scheduleNotificationAsync({
      identifier: TRIAL_REMINDER_ID,
      content: {
        title: i18n.t("notifications.trial_ends_title"),
        body: i18n.t("notifications.trial_ends_body", { price }),
        data: { type: "trial_ends" },
        sound: notificationSound(),
        ...(Platform.OS === "android" ? { channelId: AndroidNotificationChannel.reminders } : {}),
      },
      trigger: { type: Notifications.SchedulableTriggerInputTypes.DATE, date: at },
    });
    return true;
  } catch (error) {
    reportFailure("trial_reminder", error);
    return false;
  }
}

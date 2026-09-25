import * as Notifications from "expo-notifications";

/** Same indigo as `theme.primary`. */
export const BRAND_NOTIFICATION_COLOR = "#4F56E5";

export const AndroidNotificationChannel = {
  reminders: "recall-reminders",
  learning: "recall-learning",
  inbox: "recall-inbox",
} as const;

/** One short pulse. The old pattern was three long buzzes. */
export const REMINDER_VIBRATION_MS = [0, 80] as const;

const LEARNING_TYPES = new Set([
  "learning_review",
  "learning_continue",
  "learning_daily_goal",
]);

export function androidChannelForPushType(type: string | undefined): string {
  if (type && LEARNING_TYPES.has(type)) return AndroidNotificationChannel.learning;
  if (type === "email_suggestion") return AndroidNotificationChannel.inbox;
  return AndroidNotificationChannel.reminders;
}

export async function ensureAndroidNotificationChannels(names: {
  reminders: string;
  learning: string;
  inbox: string;
}): Promise<void> {
  await Notifications.setNotificationChannelAsync(AndroidNotificationChannel.reminders, {
    name: names.reminders,
    importance: Notifications.AndroidImportance.HIGH,
    vibrationPattern: [...REMINDER_VIBRATION_MS],
    enableVibrate: true,
  });
  await Notifications.setNotificationChannelAsync(AndroidNotificationChannel.learning, {
    name: names.learning,
    importance: Notifications.AndroidImportance.DEFAULT,
    enableVibrate: false,
  });
  await Notifications.setNotificationChannelAsync(AndroidNotificationChannel.inbox, {
    name: names.inbox,
    importance: Notifications.AndroidImportance.DEFAULT,
    enableVibrate: false,
  });
}

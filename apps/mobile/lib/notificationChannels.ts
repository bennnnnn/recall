import * as Notifications from "expo-notifications";

/** Same indigo as `theme.primary`. */
export const BRAND_NOTIFICATION_COLOR = "#4F56E5";

/** Installs that send this created the v2 channels, which carry the custom cue. */
export const TONE_ANDROID_CHANNELS = "tone";

/** Bundled in app.json. Android resource name is the basename. */
export const NOTIFICATION_SOUND = "recall_notify.wav";

export const AndroidNotificationChannel = {
  reminders: "recall-reminders-v2",
  inbox: "recall-inbox-v2",
} as const;

/** One short pulse. The old pattern was three long buzzes. */
export const REMINDER_VIBRATION_MS = [0, 80] as const;

export function androidChannelForPushType(type: string | undefined): string {
  if (type === "email_suggestion") return AndroidNotificationChannel.inbox;
  return AndroidNotificationChannel.reminders;
}

export async function ensureAndroidNotificationChannels(names: {
  reminders: string;
  inbox: string;
}): Promise<void> {
  // Android locks a channel's sound at creation, so these ids are new.
  // Older reminder and inbox channels stay on the device.
  const sound = NOTIFICATION_SOUND;
  await Notifications.setNotificationChannelAsync(AndroidNotificationChannel.reminders, {
    name: names.reminders,
    importance: Notifications.AndroidImportance.HIGH,
    vibrationPattern: [...REMINDER_VIBRATION_MS],
    enableVibrate: true,
    sound,
  });
  await Notifications.setNotificationChannelAsync(AndroidNotificationChannel.inbox, {
    name: names.inbox,
    importance: Notifications.AndroidImportance.DEFAULT,
    enableVibrate: false,
    sound,
  });
}

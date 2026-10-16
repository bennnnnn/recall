import * as Notifications from "expo-notifications";

/** Installs that send this created the v2 channels, which carry the custom cue. */
export const TONE_ANDROID_CHANNELS = "tone";

/** Bundled in app.json. Android resource name is the basename. */
export const NOTIFICATION_SOUND = "recall_notify.wav";

export const AndroidNotificationChannel = {
  reminders: "recall-reminders-v2",
} as const;

/** One short pulse. The old pattern was three long buzzes. */
const REMINDER_VIBRATION_MS = [0, 80] as const;

export async function ensureAndroidNotificationChannels(names: {
  reminders: string;
}): Promise<void> {
  // Android locks a channel's sound at creation, so this id is new.
  // Older reminder and inbox channels stay on the device.
  const sound = NOTIFICATION_SOUND;
  await Notifications.setNotificationChannelAsync(AndroidNotificationChannel.reminders, {
    name: names.reminders,
    importance: Notifications.AndroidImportance.HIGH,
    vibrationPattern: [...REMINDER_VIBRATION_MS],
    enableVibrate: true,
    sound,
  });
}

/**
 * Whether a saved reminder can alert, asked at the moment the user saves one.
 *
 * Local reminders run only with notification permission, and a background refresh never
 * asks for it (todoReminders.permitted); neither does the launch (pushNotifications.ts).
 * Saving a reminder with a time is an explicit action, so that is when the app asks: Recall
 * says why, then the phone's prompt follows (`askNotificationPermission`). A user who said
 * no to the phone is told once per app launch; one who said Not now to Recall is not asked
 * again until the next launch, and the phone's one prompt stays unspent.
 */
type ReminderAlerts = "on" | "off" | "not_now";

let toldAlertsOff = false;
let saidNotNow = false;

export async function allowReminderAlerts(): Promise<ReminderAlerts> {
  try {
    // Loaded on save, so every chat bubble that holds a card does not load expo-notifications.
    const push = await import("@/features/notifications/model/pushNotifications");
    if (saidNotNow) return (await push.getNotificationPermissionGranted()) ? "on" : "not_now";
    const answer = await push.askNotificationPermission();
    if (answer === "not_now") saidNotNow = true;
    return answer === "granted" ? "on" : answer === "denied" ? "off" : "not_now";
  } catch {
    return "off";
  }
}

/** True the first time alerts are off since launch, so the user is told only once. */
export function shouldTellAlertsOff(): boolean {
  if (toldAlertsOff) return false;
  toldAlertsOff = true;
  return true;
}

/** For tests: tell and ask again. */
export function resetAlertsOffNoticeForTest(): void {
  toldAlertsOff = false;
  saidNotNow = false;
}

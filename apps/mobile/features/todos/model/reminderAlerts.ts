/**
 * Whether a saved reminder can alert, asked at the moment the user saves one.
 *
 * Local reminders run only with notification permission, and a background refresh never
 * asks for it (todoReminders.permitted); neither does the launch (pushNotifications.ts).
 * Saving a reminder with a time is an explicit action, so that is when the app asks: Recall
 * says why, then the phone's prompt follows (`askNotificationPermission`). A user the phone
 * refused is told once per app launch, with Settings; one who said Not now to Recall is not
 * asked again on a save until the next launch, and the phone's one prompt stays unspent.
 */

/** `off`: the phone refused, and only Settings can turn it on. `not_now`: never refused. */
type ReminderAlerts = "on" | "off" | "not_now";

let toldAlertsOff = false;
let saidNotNow = false;

function alertsOf(answer: "granted" | "denied" | "not_now" | "askable"): ReminderAlerts {
  if (answer === "granted") return "on";
  return answer === "denied" ? "off" : "not_now";
}

export async function allowReminderAlerts(): Promise<ReminderAlerts> {
  try {
    // Loaded on save, so every chat bubble that holds a card does not load expo-notifications.
    const push = await import("@/features/notifications/model/pushNotifications");
    // After Not now, a save reads where things stand: allowed, or refused for good since (the
    // Settings switch's ask), which only Settings can undo.
    if (saidNotNow) return alertsOf(await push.notificationPermissionState());
    const answer = await push.askNotificationPermission();
    saidNotNow = answer === "not_now";
    return alertsOf(answer);
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

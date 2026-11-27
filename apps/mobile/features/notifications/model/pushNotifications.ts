import Constants from "expo-constants";
import * as Notifications from "expo-notifications";
import { type AppStateStatus, Platform } from "react-native";

import type { ActionFeedbackApi } from "@/contexts/actionFeedbackCore";
import { api } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { FOREGROUND_STALE_MS, onAppStateChange } from "@/lib/foregroundRefresh";
import { isExpoGo, isPhysicalDevice } from "@/lib/expoRuntime";
import i18n from "@/lib/i18n";
import { getInstallationId } from "@/lib/installationId";
import { trackProductEvent } from "@/lib/productAnalytics";
import {
  ensureAndroidNotificationChannels,
  TONE_ANDROID_CHANNELS,
} from "@/features/notifications/model/notificationChannels";
import { reportRecoverableWarning } from "@/lib/reportRecoverableError";
import { confirmDialog } from "@/ui/overlay/dialogs";
import { reportFailure } from "@/lib/sentry";
import { devicePushTokenFingerprint } from "@/features/notifications/model/devicePushToken";
import { forgetSyncRecords, recentSyncAt, recordSync } from "@/lib/syncRecords";
import { setRemotePushRegistered } from "@/features/notifications/model/pushRegistration";

type AppRouter = {
  push: (href: unknown) => void;
  replace: (href: unknown) => void;
};

let androidChannelReady = false;

export async function getNotificationPermissionGranted(): Promise<boolean> {
  const { status } = await Notifications.getPermissionsAsync();
  return status === "granted";
}

/**
 * What asking for notifications came to: allowed; refused by the phone, so only Settings can
 * turn it on; or `not_now`, the user's answer to Recall's explanation, with the phone's own
 * prompt still unspent.
 */
type NotificationAsk = "granted" | "denied" | "not_now";

/**
 * Asks for notifications on the user's own step (a reminder saved, the Notifications switch
 * turned on, a trial reminder), never at launch. iOS shows its prompt once, so Recall says
 * why first (`confirmDialog`) and the phone asks only on Continue. Granted already, or
 * refused for good (`canAskAgain` false), asks nothing.
 */
export async function askNotificationPermission(): Promise<NotificationAsk> {
  await ensureReminderChannel();
  const existing = await Notifications.getPermissionsAsync();
  if (existing.status === "granted") return "granted";
  if (existing.canAskAgain === false) return "denied";
  const proceed = await confirmDialog({
    title: i18n.t("permissions.notifications_ask_title"),
    message: i18n.t("permissions.notifications_ask_body"),
    cancelLabel: i18n.t("common.not_now"),
    confirmLabel: i18n.t("permissions.notifications_ask_continue"),
  });
  if (!proceed) return "not_now";
  const { status } = await Notifications.requestPermissionsAsync();
  trackProductEvent("push_permission", {
    status: status === "granted" ? "granted" : "denied",
  });
  return status === "granted" ? "granted" : "denied";
}

/** `askNotificationPermission`, for a caller that needs only whether alerts can show. */
export async function ensureNotificationPermission(): Promise<boolean> {
  return (await askNotificationPermission()) === "granted";
}

/** The reminders channel push and local reminders share, created once per run. */
export async function ensureReminderChannel(): Promise<void> {
  if (Platform.OS !== "android" || androidChannelReady) return;
  await ensureAndroidNotificationChannels({
    reminders: i18n.t("notifications.reminders_channel"),
  });
  androidChannelReady = true;
}

function resolveEasProjectId(): string | null {
  const fromExtra = Constants.expoConfig?.extra?.eas?.projectId;
  if (typeof fromExtra === "string" && fromExtra.trim()) {
    return fromExtra.trim();
  }
  const fromEas = Constants.easConfig?.projectId;
  if (typeof fromEas === "string" && fromEas.trim()) {
    return fromEas.trim();
  }
  return null;
}

/** Offline is routine: the next sync asks again. */
const TOKEN_NETWORK_ERROR = "ERR_NOTIFICATIONS_NETWORK_ERROR";
let pushTokenFailureReported = false;

function errorCode(error: unknown): string | null {
  if (typeof error !== "object" || error === null || !("code" in error)) return null;
  return typeof error.code === "string" ? error.code : null;
}

/**
 * No token is routine offline, in Expo Go, on a simulator and with notifications denied.
 * Anything else leaves push off while the setting says on, so the user hears it once per
 * app run. Logs carry the error code only: Expo's messages can include the device token.
 */
async function reportPushTokenFailure(
  error: unknown,
  feedback?: ActionFeedbackApi | null,
): Promise<void> {
  const code = errorCode(error);
  if (code === TOKEN_NETWORK_ERROR || isExpoGo() || isPhysicalDevice() === false) return;
  // A permission that cannot be read is not a known routine state.
  if (!(await getNotificationPermissionGranted().catch(() => true))) return;
  console.warn(`[push] no push token: ${code ?? "uncoded error"}`);
  if (!feedback || pushTokenFailureReported) return;
  pushTokenFailureReported = true;
  reportRecoverableWarning(feedback, i18n.t("notifications.push_unavailable"));
}

/**
 * `feedback` is for callers with no failure report of their own (the background sync);
 * the Settings switch reports a failed registration itself.
 */
async function resolveExpoPushToken(
  feedback?: ActionFeedbackApi | null,
): Promise<string | null> {
  const projectId = resolveEasProjectId();
  // Without an EAS project id (Expo Go, a local build) there is no push token: normal there.
  if (!projectId) return null;
  try {
    const tokenData = await Notifications.getExpoPushTokenAsync({ projectId });
    return tokenData.data || null;
  } catch (error) {
    await reportPushTokenFailure(error, feedback);
    return null;
  }
}

type PushRegisterResult = "registered" | "skipped" | "no_permission";

/** Register Expo push token with the backend for remote notifications.
 *
 * Gated on ``pushNotificationsEnabled`` (the user's ``push_notifications_enabled``
 * pref): when the user has disabled push, we must NOT register the token —
 * without this gate, the backend would hold a live push token for a user who
 * opted out and keep sending them notifications.
 *
 * It never asks for the OS permission: that is `askNotificationPermission`, on the user's own
 * step. Without the permission it registers nothing and leaves the account's switch alone
 * (`no_permission`): a cold prompt at launch spent iOS's one ask, and a "Don't allow" there
 * turned reminders off on the server, so allowing them later in Settings brought nothing
 * back. The server skips a user with no device token (todos/due_reminders.py), and the next
 * sync after a grant registers.
 */
export async function registerRemotePushToken(
  apiToken: string,
  pushNotificationsEnabled: boolean,
  feedback?: ActionFeedbackApi | null,
): Promise<PushRegisterResult> {
  if (!pushNotificationsEnabled) {
    setRemotePushRegistered(false);
    return "skipped";
  }
  await ensureReminderChannel();
  if (!(await getNotificationPermissionGranted())) {
    setRemotePushRegistered(false);
    return "no_permission";
  }

  const expoPushToken = await resolveExpoPushToken(feedback);
  if (!expoPushToken) {
    setRemotePushRegistered(false);
    throw new Error("push_token_unavailable");
  }

  const deviceId = await getInstallationId();
  await api.registerPushToken(apiToken, {
    expo_push_token: expoPushToken,
    platform: Platform.OS,
    device_id: deviceId ?? undefined,
    ...(Platform.OS === "android" ? { android_channels: TONE_ANDROID_CHANNELS } : {}),
  });
  setRemotePushRegistered(true);
  return "registered";
}

/** This device's Expo push token, for sign-out to hand the server; null when this device
 * cannot have registered one (Expo Go, no notification permission). */
export async function devicePushToken(): Promise<string | null> {
  if (!(await getNotificationPermissionGranted())) return null;
  return resolveExpoPushToken();
}

/** Unregister the Expo push token from the backend.
 *
 * Called when the user disables ``push_notifications_enabled`` — without
 * this, the backend keeps a live push token for a user who opted out and
 * continues sending them notifications. Best-effort: a network failure here
 * doesn't block the pref change (the next foreground sync retries).
 */
export async function unregisterRemotePushToken(
  apiToken: string,
  feedback?: ActionFeedbackApi | null,
): Promise<boolean> {
  // Off means the server stops sending, so the phone takes its reminders back now.
  setRemotePushRegistered(false);
  const expoPushToken = await resolveExpoPushToken(feedback);
  if (!expoPushToken) return false;
  try {
    await api.unregisterPushToken(apiToken, { expo_push_token: expoPushToken });
    return true;
  } catch (error) {
    reportFailure("push_unregister", error);
    return false;
  }
}

/**
 * The background sync runs on launch, on every access-token refresh (the
 * effect re-attaches hourly) and on every return to the app. Each run asked
 * Expo's push service for the token and posted it to our API. After a sync
 * succeeds for this account and setting, later runs only re-check the OS
 * permission (local) until this long has passed; a failure retries next time.
 * The time is also kept for the account and this install's push token
 * (`lib/syncRecords.ts`, forgotten at sign-in and sign-out), so a cold start
 * inside the window does not register again unless the token changed.
 */
const PUSH_RESYNC_INTERVAL_MS = FOREGROUND_STALE_MS.pushRegistration;
let lastPushSync: { session: number; account: string | undefined; enabled: boolean; at: number } | null = null;

function pushSyncIsFresh(session: number, account: string | undefined, enabled: boolean): boolean {
  if (lastPushSync == null) return false;
  const age = Date.now() - lastPushSync.at;
  return (
    lastPushSync.session === session &&
    lastPushSync.account === account &&
    lastPushSync.enabled === enabled &&
    // A clock set back makes the age negative: not trusted as recent.
    age >= 0 && age < PUSH_RESYNC_INTERVAL_MS
  );
}

/** Sign-out: the next sign-in, whoever's, registers this device again. */
export async function clearPushSyncRecord(): Promise<void> {
  lastPushSync = null;
  setRemotePushRegistered(false);
  await forgetSyncRecords();
}

/**
 * `account` is the signed-in user's id: it also finds a sync an earlier launch
 * made for this sign-in. Another account signing in on this device rebinds the
 * token, so a sync never counts across sign-ins. `feedback` shows a push token
 * failure that is not routine (see reportPushTokenFailure).
 *
 * It never prompts: without the permission it registers nothing, and a return to the app
 * after the user allowed notifications (in Settings, or a reminder's ask) registers then.
 */
export function attachPushForegroundSync(
  apiToken: string | null,
  pushNotificationsEnabled: boolean,
  account?: string,
  feedback?: ActionFeedbackApi | null,
): () => void {
  if (!apiToken) return () => {};
  const session = getSessionGeneration();

  const syncNow = async () => {
    const enabled = pushNotificationsEnabled;
    // Not allowed (yet): nothing to register, and nothing to ask the push service for.
    if (enabled && !(await getNotificationPermissionGranted())) {
      lastPushSync = null;
      return setRemotePushRegistered(false);
    }
    // The saved record's key: the setting and the token it registered, so a
    // token the push service rolled since registers again.
    let savedKey: string | null = null;
    if (!pushSyncIsFresh(session, account, enabled) && account) {
      const device = await devicePushTokenFingerprint();
      if (device !== null) {
        savedKey = `${enabled ? "on" : "off"}:${device}`;
        const at = await recentSyncAt("push", account, PUSH_RESYNC_INTERVAL_MS, savedKey);
        if (at !== null) lastPushSync = { session, account, enabled, at };
      }
    }
    if (pushSyncIsFresh(session, account, enabled)) {
      // Turning the permission off in Settings must still reach the server.
      if (!enabled) return setRemotePushRegistered(false);
      // A sync an earlier launch made, and still allowed (read above): the server holds this token.
      return setRemotePushRegistered(true);
    }
    lastPushSync = null;
    const remember = () => {
      // A sync that finishes after sign-out must not vouch for the next sign-in.
      if (session !== getSessionGeneration()) return;
      const at = Date.now();
      lastPushSync = { session, account, enabled, at };
      if (account && savedKey !== null) void recordSync("push", account, savedKey, at);
    };
    if (enabled) {
      if ((await registerRemotePushToken(apiToken, true, feedback)) === "registered") remember();
    } else if (await unregisterRemotePushToken(apiToken, feedback)) {
      remember();
    }
  };
  const sync = () => {
    void syncNow().catch(() => {});
  };

  // Register when enabled, unregister when disabled — so toggling the pref
  // actually stops (or starts) backend delivery, not just OS permission.
  sync();

  return onAppStateChange((state: AppStateStatus) => {
    if (state === "active") sync();
  });
}

type PushData = {
  run_id?: unknown;
  type?: string;
  screen?: string;
  focus?: string;
  todo_id?: string;
  profile_id?: string;
  topic?: string;
};

/** Push when the target is a different screen; replace when already on it so
 * repeated taps never stack duplicate copies of the same route. */
function navigateToTarget(
  router: AppRouter,
  currentPathname: string | null,
  href: string | { pathname: string; params?: Record<string, string> },
): void {
  const target = typeof href === "string" ? href : href.pathname;
  if (currentPathname && currentPathname === target) {
    router.replace(href);
  } else {
    router.push(href);
  }
}

/** Navigate when the user taps a push notification. */
export async function handlePushNotificationResponse(
  router: AppRouter,
  data: PushData | undefined,
  currentPathname?: string | null,
): Promise<void> {
  if (!data) return;
  const current = currentPathname ?? null;

  if (data.type === "todo_due" || data.type === "todo_reminder" || data.screen === "todos") {
    navigateToTarget(router, current, {
      pathname: "/todos",
      params: data.todo_id ? { highlight: data.todo_id } : {},
    });
  }
}

export function configurePushNotificationHandler(): void {
  void ensureReminderChannel();
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: true,
      shouldSetBadge: false,
    }),
  });
}

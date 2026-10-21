import Constants from "expo-constants";
import * as Notifications from "expo-notifications";
import { AppState, type AppStateStatus, Platform } from "react-native";

import type { ActionFeedbackApi } from "@/contexts/actionFeedbackCore";
import { api } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { cacheFile } from "@/lib/cache/cacheFile";
import { isExpoGo, isPhysicalDevice } from "@/lib/expoRuntime";
import i18n from "@/lib/i18n";
import { getInstallationId } from "@/lib/installationId";
import { trackProductEvent } from "@/lib/productAnalytics";
import {
  ensureAndroidNotificationChannels,
  TONE_ANDROID_CHANNELS,
} from "@/lib/notificationChannels";
import { reportRecoverableWarning } from "@/lib/reportRecoverableError";

type AppRouter = {
  push: (href: unknown) => void;
  replace: (href: unknown) => void;
};

let androidChannelReady = false;

export async function getNotificationPermissionGranted(): Promise<boolean> {
  if (Platform.OS === "web") return false;
  const { status } = await Notifications.getPermissionsAsync();
  return status === "granted";
}

export async function ensureNotificationPermission(): Promise<boolean> {
  if (Platform.OS === "web") return false;
  await ensureAndroidChannel();
  const { status: existing } = await Notifications.getPermissionsAsync();
  if (existing === "granted") return true;
  const { status } = await Notifications.requestPermissionsAsync();
  trackProductEvent("push_permission", {
    status: status === "granted" ? "granted" : "denied",
  });
  return status === "granted";
}

async function ensureAndroidChannel(): Promise<void> {
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

type PushRegisterResult = "registered" | "skipped" | "disabled_permission";

/** Register Expo push token with the backend for remote notifications.
 *
 * Gated on ``pushNotificationsEnabled`` (the user's ``push_notifications_enabled``
 * pref): when the user has disabled push, we must NOT register the token —
 * without this gate, the backend would hold a live push token for a user who
 * opted out and keep sending them notifications. The OS-level permission
 * prompt is separate (and still required); this gate is the user-level opt-out.
 *
 * If the pref is on but the OS denies permission, flip the server pref off so
 * Settings and local/catch-up delivery agree (remote + local both fail on iOS
 * without permission; the pref lie is what froze recurring catch-up).
 */
export async function registerRemotePushToken(
  apiToken: string,
  pushNotificationsEnabled: boolean,
  feedback?: ActionFeedbackApi | null,
): Promise<PushRegisterResult> {
  if (Platform.OS === "web") return "skipped";
  if (!pushNotificationsEnabled) return "skipped";
  const granted = await ensureNotificationPermission();
  if (!granted) {
    await api.updateMe(apiToken, { push_notifications_enabled: false });
    return "disabled_permission";
  }

  const expoPushToken = await resolveExpoPushToken(feedback);
  if (!expoPushToken) {
    throw new Error("push_token_unavailable");
  }

  const deviceId = await getInstallationId();
  await api.registerPushToken(apiToken, {
    expo_push_token: expoPushToken,
    platform: Platform.OS,
    device_id: deviceId ?? undefined,
    ...(Platform.OS === "android" ? { android_channels: TONE_ANDROID_CHANNELS } : {}),
  });
  return "registered";
}

/** This device's Expo push token, for sign-out to hand the server; null when this device
 * cannot have registered one (web, Expo Go, no notification permission). */
export async function devicePushToken(): Promise<string | null> {
  if (Platform.OS === "web") return null;
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
  if (Platform.OS === "web") return true;
  const expoPushToken = await resolveExpoPushToken(feedback);
  if (!expoPushToken) return false;
  try {
    await api.unregisterPushToken(apiToken, { expo_push_token: expoPushToken });
    return true;
  } catch {
    /* best-effort */
    return false;
  }
}

/**
 * The background sync runs on launch, on every access-token refresh (the
 * effect re-attaches hourly) and on every return to the app. Each run asked
 * Expo's push service for the token and posted it to our API. After a sync
 * succeeds for this account and setting, later runs only re-check the OS
 * permission (local) until this long has passed; a failure retries next time.
 */
const PUSH_RESYNC_INTERVAL_MS = 12 * 60 * 60_000;
/**
 * The last sync that succeeded, on disk: in module memory it was lost with every
 * process, so each cold start asked Expo and our API again (code-health audit
 * NET-19). Sign-out clears it, since the server forgets the device's token with
 * the session.
 */
const pushSyncFile = cacheFile("push-sync.json");
type PushSyncRecord = { account: string; enabled: boolean; at: number };

async function readPushSync(): Promise<PushSyncRecord | null> {
  const raw = await pushSyncFile.read();
  if (!raw) return null;
  try {
    const record = JSON.parse(raw) as Partial<PushSyncRecord> | null;
    if (typeof record?.account === "string" && typeof record.enabled === "boolean" &&
      typeof record.at === "number") {
      return { account: record.account, enabled: record.enabled, at: record.at };
    }
  } catch {
    /* unreadable: sync again */
  }
  return null;
}

function pushSyncIsFresh(record: PushSyncRecord | null, account: string | undefined, enabled: boolean): boolean {
  return (
    account !== undefined &&
    record != null &&
    record.account === account &&
    record.enabled === enabled &&
    Date.now() - record.at < PUSH_RESYNC_INTERVAL_MS
  );
}

/** Sign-out: the next sign-in, whoever's, registers this device again. */
export function clearPushSyncRecord(): Promise<void> {
  return pushSyncFile.clear();
}

/**
 * `account` is the signed-in user's id; without it every run syncs. Another
 * account signing in on this device rebinds the token, so a sync never counts
 * for another account. `feedback` shows a push token failure that is not
 * routine (see reportPushTokenFailure).
 */
export function attachPushForegroundSync(
  apiToken: string | null,
  pushNotificationsEnabled: boolean,
  onPushPrefChange?: (enabled: boolean) => void,
  account?: string,
  feedback?: ActionFeedbackApi | null,
): () => void {
  if (!apiToken) return () => {};
  const session = getSessionGeneration();

  const syncNow = async () => {
    const enabled = pushNotificationsEnabled;
    if (pushSyncIsFresh(await readPushSync(), account, enabled)) {
      // Turning the permission off in Settings must still reach the server.
      if (!enabled || (await getNotificationPermissionGranted())) return;
    }
    await pushSyncFile.clear();
    const remember = async () => {
      // A sync that finishes after sign-out must not vouch for the next sign-in.
      if (account === undefined || session !== getSessionGeneration()) return;
      await pushSyncFile.write(JSON.stringify({ account, enabled, at: Date.now() }));
    };
    if (enabled) {
      const result = await registerRemotePushToken(apiToken, true, feedback);
      if (result === "registered") await remember();
      if (result === "disabled_permission") onPushPrefChange?.(false);
    } else if (await unregisterRemotePushToken(apiToken, feedback)) {
      await remember();
    }
  };
  const sync = () => {
    void syncNow().catch(() => {});
  };

  // Register when enabled, unregister when disabled — so toggling the pref
  // actually stops (or starts) backend delivery, not just OS permission.
  sync();

  const onChange = (state: AppStateStatus) => {
    if (state === "active") sync();
  };

  const sub = AppState.addEventListener("change", onChange);
  return () => sub.remove();
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
  void ensureAndroidChannel();
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: true,
      shouldSetBadge: false,
    }),
  });
}

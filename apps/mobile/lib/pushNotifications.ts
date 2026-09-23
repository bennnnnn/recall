import Constants from "expo-constants";
import * as Notifications from "expo-notifications";
import { AppState, type AppStateStatus, Platform } from "react-native";

import { api } from "@/lib/api";
import i18n from "@/lib/i18n";
import { getInstallationId } from "@/lib/installationId";
import { trackProductEvent } from "@/lib/productAnalytics";
import { lessonMapPath } from "@/features/learning/model/chapterAccess";

type AppRouter = {
  push: (href: unknown) => void;
  replace: (href: unknown) => void;
};

let androidChannelReady = false;
const ANDROID_CHANNEL = "recall-notifications";

export async function getNotificationPermissionGranted(): Promise<boolean> {
  if (Platform.OS === "web") return false;
  const { status } = await Notifications.getPermissionsAsync();
  return status === "granted";
}

export async function ensureNotificationPermission(analyticsToken?: string): Promise<boolean> {
  if (Platform.OS === "web") return false;
  await ensureAndroidChannel();
  const { status: existing } = await Notifications.getPermissionsAsync();
  if (existing === "granted") return true;
  const { status } = await Notifications.requestPermissionsAsync();
  trackProductEvent(analyticsToken ?? null, "push_permission", {
    status: status === "granted" ? "granted" : "denied",
  });
  return status === "granted";
}

async function ensureAndroidChannel(): Promise<void> {
  if (Platform.OS !== "android" || androidChannelReady) return;
  await Notifications.setNotificationChannelAsync(ANDROID_CHANNEL, {
    name: i18n.t("notifications.app_channel"),
    importance: Notifications.AndroidImportance.HIGH,
    vibrationPattern: [0, 250, 250, 250],
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

async function resolveExpoPushToken(): Promise<string | null> {
  const projectId = resolveEasProjectId();
  if (!projectId) return null;
  try {
    const tokenData = await Notifications.getExpoPushTokenAsync({ projectId });
    return tokenData.data || null;
  } catch {
    return null;
  }
}

export type PushRegisterResult = "registered" | "skipped" | "disabled_permission";

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
): Promise<PushRegisterResult> {
  if (Platform.OS === "web") return "skipped";
  if (!pushNotificationsEnabled) return "skipped";
  const granted = await ensureNotificationPermission(apiToken);
  if (!granted) {
    await api.updateMe(apiToken, { push_notifications_enabled: false });
    return "disabled_permission";
  }

  const expoPushToken = await resolveExpoPushToken();
  if (!expoPushToken) {
    throw new Error("push_token_unavailable");
  }

  const deviceId = await getInstallationId();
  await api.registerPushToken(apiToken, {
    expo_push_token: expoPushToken,
    platform: Platform.OS,
    device_id: deviceId ?? undefined,
  });
  return "registered";
}

/** Unregister the Expo push token from the backend.
 *
 * Called when the user disables ``push_notifications_enabled`` — without
 * this, the backend keeps a live push token for a user who opted out and
 * continues sending them notifications. Best-effort: a network failure here
 * doesn't block the pref change (the next foreground sync retries).
 */
export async function unregisterRemotePushToken(apiToken: string): Promise<void> {
  if (Platform.OS === "web") return;
  const expoPushToken = await resolveExpoPushToken();
  if (!expoPushToken) return;
  try {
    await api.unregisterPushToken(apiToken, { expo_push_token: expoPushToken });
  } catch {
    /* best-effort */
  }
}

export function attachPushForegroundSync(
  apiToken: string | null,
  pushNotificationsEnabled: boolean,
  onPushPrefChange?: (enabled: boolean) => void,
): () => void {
  if (!apiToken) return () => {};

  const sync = () => {
    if (pushNotificationsEnabled) {
      void registerRemotePushToken(apiToken, true)
        .then((result) => {
          if (result === "disabled_permission") onPushPrefChange?.(false);
        })
        .catch(() => {});
    } else {
      void unregisterRemotePushToken(apiToken);
    }
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
  type?: string;
  screen?: string;
  focus?: string;
  todo_id?: string;
  project_id?: string;
  profile_id?: string;
  topic?: string;
  event_start?: string;
  event_id?: string;
  event_title?: string;
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

  if (data.type === "job_search_ready" || data.screen === "my-job") {
    navigateToTarget(router, current, "/my-job");
    return;
  }

  if (data.type === "calendar_nudge") {
    // The To-do screen no longer owns a calendar wall. Carry the exact event
    // context so the notification opens a focused card instead of a dead date.
    if (data.event_title && data.event_start) {
      navigateToTarget(router, current, {
        pathname: "/todos",
        params: {
          eventTitle: data.event_title,
          eventStart: data.event_start,
          ...(data.event_id ? { eventId: data.event_id } : {}),
        },
      });
    } else {
      navigateToTarget(router, current, "/");
    }
    return;
  }

  if (data.type === "todo_due" || data.type === "todo_reminder" || data.screen === "todos") {
    navigateToTarget(router, current, {
      pathname: "/todos",
      params: data.todo_id ? { highlight: data.todo_id } : {},
    });
    return;
  }

  if (
    (data.type === "learning_review" ||
      data.type === "learning_continue" ||
      data.type === "learning_daily_goal") &&
    data.project_id
  ) {
    // Straight to the lesson map — /projects/:id is just a redirect hop.
    navigateToTarget(router, current, lessonMapPath(data.project_id));
    return;
  }

  // To-do renders pending Gmail suggestions with Add and Dismiss actions.
  if (data.type === "email_suggestion") {
    navigateToTarget(router, current, "/todos");
    return;
  }

  if (data.project_id) {
    navigateToTarget(router, current, lessonMapPath(data.project_id));
  }
}

export function configurePushNotificationHandler(): void {
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: true,
      shouldSetBadge: false,
    }),
  });
}

import Constants from "expo-constants";
import * as Notifications from "expo-notifications";
import { AppState, type AppStateStatus, Platform } from "react-native";

import { api } from "@/lib/api";
import i18n from "@/lib/i18n";

type AppRouter = {
  push: (href: unknown) => void;
  replace: (href: unknown) => void;
};

let androidChannelReady = false;
const ANDROID_CHANNEL = "recall-notifications";

export async function ensureNotificationPermission(): Promise<boolean> {
  if (Platform.OS === "web") return false;
  await ensureAndroidChannel();
  const { status: existing } = await Notifications.getPermissionsAsync();
  if (existing === "granted") return true;
  const { status } = await Notifications.requestPermissionsAsync();
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

/** Register Expo push token with the backend for remote notifications.
 *
 * Gated on ``pushNotificationsEnabled`` (the user's ``push_notifications_enabled``
 * pref): when the user has disabled push, we must NOT register the token —
 * without this gate, the backend would hold a live push token for a user who
 * opted out and keep sending them notifications. The OS-level permission
 * prompt is separate (and still required); this gate is the user-level opt-out.
 */
export async function registerRemotePushToken(
  apiToken: string,
  pushNotificationsEnabled: boolean,
): Promise<void> {
  if (Platform.OS === "web") return;
  if (!pushNotificationsEnabled) return;
  const granted = await ensureNotificationPermission();
  if (!granted) return;

  const expoPushToken = await resolveExpoPushToken();
  if (!expoPushToken) return;

  try {
    const deviceId =
      typeof Constants.installationId === "string" && Constants.installationId.trim()
        ? Constants.installationId.trim()
        : undefined;
    await api.registerPushToken(apiToken, {
      expo_push_token: expoPushToken,
      platform: Platform.OS,
      device_id: deviceId,
    });
  } catch {
    /* best-effort */
  }
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
): () => void {
  if (!apiToken) return () => {};

  // Register when enabled, unregister when disabled — so toggling the pref
  // actually stops (or starts) backend delivery, not just OS permission.
  if (pushNotificationsEnabled) {
    void registerRemotePushToken(apiToken, true);
  } else {
    void unregisterRemotePushToken(apiToken);
  }

  const onChange = (state: AppStateStatus) => {
    if (state === "active") {
      if (pushNotificationsEnabled) {
        void registerRemotePushToken(apiToken, true);
      } else {
        void unregisterRemotePushToken(apiToken);
      }
    }
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
  topic?: string;
};

async function openLearningProject(
  router: AppRouter,
  _apiToken: string,
  projectId: string,
  _topic?: string,
): Promise<void> {
  router.push(`/projects/${projectId}`);
}

/** Navigate when the user taps a push notification. */
export async function handlePushNotificationResponse(
  router: AppRouter,
  apiToken: string | null,
  data: PushData | undefined,
): Promise<void> {
  if (!data) return;

  if (data.type === "calendar_nudge") {
    router.push({ pathname: "/todos", params: { focus: "reminders" } });
    return;
  }

  if (data.type === "todo_due" || data.type === "todo_reminder" || data.screen === "todos") {
    router.push({
      pathname: "/todos",
      params: {
        focus: data.focus ?? "reminders",
        ...(data.todo_id ? { highlight: data.todo_id } : {}),
      },
    });
    return;
  }

  if (
    (data.type === "learning_review" ||
      data.type === "learning_continue" ||
      data.type === "learning_daily_goal" ||
      data.type === "email_suggestion") &&
    apiToken &&
    data.project_id
  ) {
    await openLearningProject(router, apiToken, data.project_id, data.topic);
    return;
  }

  if (data.type === "email_suggestion") {
    router.push({ pathname: "/todos", params: { focus: "reminders" } });
    return;
  }

  if (data.project_id) {
    router.push(`/projects/${data.project_id}`);
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

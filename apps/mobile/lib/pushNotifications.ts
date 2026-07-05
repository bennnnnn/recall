import Constants from "expo-constants";
import * as Notifications from "expo-notifications";
import { AppState, type AppStateStatus, Platform } from "react-native";

import { api } from "@/lib/api";

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
    name: "Recall",
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

/** Register Expo push token with the backend for remote notifications. */
export async function registerRemotePushToken(apiToken: string): Promise<void> {
  if (Platform.OS === "web") return;
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

export function attachPushForegroundSync(apiToken: string | null): () => void {
  if (!apiToken) return () => {};

  void registerRemotePushToken(apiToken);

  const onChange = (state: AppStateStatus) => {
    if (state === "active") {
      void registerRemotePushToken(apiToken);
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

import Constants from "expo-constants";
import * as Notifications from "expo-notifications";
import { AppState, type AppStateStatus, Platform } from "react-native";

import { api } from "@/lib/api";
import { getInstallationId } from "@/lib/installationId";
import type { AppRouter } from "@/lib/router";

const ANDROID_CHANNEL_ID = "default";

function projectId(): string | undefined {
  return (
    Constants.expoConfig?.extra?.eas?.projectId ??
    (Constants as unknown as { easConfig?: { projectId?: string } }).easConfig?.projectId
  );
}

async function ensureAndroidChannel(): Promise<void> {
  if (Platform.OS !== "android") return;
  await Notifications.setNotificationChannelAsync(ANDROID_CHANNEL_ID, {
    name: "Recall",
    importance: Notifications.AndroidImportance.HIGH,
    sound: "default",
  });
}

export async function registerRemotePushToken(
  apiToken: string,
  requestPermission = false,
): Promise<"registered" | "disabled_permission" | "unavailable"> {
  await ensureAndroidChannel();

  let permission = await Notifications.getPermissionsAsync();
  if (requestPermission && permission.status !== "granted") {
    permission = await Notifications.requestPermissionsAsync();
  }
  if (permission.status !== "granted") return "disabled_permission";

  const easProjectId = projectId();
  if (!easProjectId) return "unavailable";

  const token = (await Notifications.getExpoPushTokenAsync({ projectId: easProjectId })).data;
  if (!token) return "unavailable";

  const installationId = await getInstallationId();
  await api.registerPushToken(apiToken, {
    expo_push_token: token,
    platform: Platform.OS,
    device_id: installationId,
  });
  return "registered";
}

export async function unregisterRemotePushToken(apiToken: string): Promise<void> {
  const permission = await Notifications.getPermissionsAsync();
  if (permission.status !== "granted") return;

  const easProjectId = projectId();
  if (!easProjectId) return;

  try {
    const token = (await Notifications.getExpoPushTokenAsync({ projectId: easProjectId })).data;
    if (token) await api.unregisterPushToken(apiToken, token);
  } catch {
    // The user already disabled notifications or the device is temporarily
    // offline. The server preference still stops delivery.
  }
}

export function keepRemotePushRegistrationFresh(
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
  topic?: string;
  automation_id?: string;
  chat_id?: string;
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

  if (data.type === "automation_run") {
    // The Tasks-style detail page is deliberately configuration-only. A run
    // notification opens the dedicated result conversation so the completed
    // answer remains accessible instead of being hidden behind task settings.
    if (data.chat_id) {
      router.push({ pathname: "/open-chat", params: { chatId: data.chat_id } });
    } else if (data.automation_id) {
      router.push(`/automations/${data.automation_id}`);
    } else {
      router.push("/automations");
    }
    return;
  }

  if (data.screen === "automations") {
    if (data.automation_id) router.push(`/automations/${data.automation_id}`);
    else router.push("/automations");
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

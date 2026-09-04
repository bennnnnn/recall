import { useEffect } from "react";
import * as Notifications from "expo-notifications";
import { useRouter } from "expo-router";
import { Platform } from "react-native";

import { useAuthOptional } from "@/contexts/AuthContext";
import {
  configurePushNotificationHandler,
  handlePushNotificationResponse,
} from "@/lib/pushNotifications";
import {
  cancelTodoReminder,
} from "@/lib/todos/todoReminders";
import {
  isRemotePushTrigger,
  todoIdFromNotificationData,
} from "@/lib/todos/todoReminderPush";

/** Handles push notification taps and configures foreground display. */
export function PushNotificationBootstrap() {
  const router = useRouter();
  const auth = useAuthOptional();
  const token = auth?.token ?? null;

  useEffect(() => {
    configurePushNotificationHandler();
  }, []);

  useEffect(() => {
    // getLastNotificationResponseAsync/addNotificationResponseReceivedListener
    // are unimplemented on web (expo-notifications throws "not available on
    // web" rather than resolving/no-op'ing), which otherwise crashes the
    // whole app on load via an uncaught rejection.
    if (Platform.OS === "web") return;

    let active = true;

    const navigate = (data: Record<string, unknown> | undefined) => {
      if (!active) return;
      void handlePushNotificationResponse(
        router as Parameters<typeof handlePushNotificationResponse>[0],
        token,
        data as never,
      ).catch(() => {
        if (active) console.warn("[notifications] Could not open notification");
      });
    };

    void Notifications.getLastNotificationResponseAsync().then((response) => {
      if (response) {
        navigate(response.notification.request.content.data as Record<string, unknown>);
      }
    }).catch(() => {
      if (active) console.warn("[notifications] Could not restore startup notification");
    });

    const responseSub = Notifications.addNotificationResponseReceivedListener((response) => {
      navigate(response.notification.request.content.data as Record<string, unknown>);
    });
    const receivedSub = Notifications.addNotificationReceivedListener((notification) => {
      if (!active) return;
      if (!isRemotePushTrigger(notification.request.trigger)) return;
      const todoId = todoIdFromNotificationData(
        notification.request.content.data as Record<string, unknown>,
      );
      if (todoId) void cancelTodoReminder(todoId).catch(() => {
        if (active) console.warn("[notifications] Could not cancel duplicate reminder");
      });
    });
    return () => {
      active = false;
      responseSub.remove();
      receivedSub.remove();
    };
  }, [router, token]);

  return null;
}

import { useEffect } from "react";
import * as Notifications from "expo-notifications";
import { useRouter } from "expo-router";

import { useAuthOptional } from "@/contexts/AuthContext";
import {
  configurePushNotificationHandler,
  handlePushNotificationResponse,
} from "@/lib/pushNotifications";

/** Handles push notification taps and configures foreground display. */
export function PushNotificationBootstrap() {
  const router = useRouter();
  const auth = useAuthOptional();
  const token = auth?.token ?? null;

  useEffect(() => {
    configurePushNotificationHandler();
  }, []);

  useEffect(() => {
    const navigate = (data: Record<string, unknown> | undefined) => {
      void handlePushNotificationResponse(
        router as Parameters<typeof handlePushNotificationResponse>[0],
        token,
        data as never,
      );
    };

    void Notifications.getLastNotificationResponseAsync().then((response) => {
      if (response) {
        navigate(response.notification.request.content.data as Record<string, unknown>);
      }
    });

    const sub = Notifications.addNotificationResponseReceivedListener((response) => {
      navigate(response.notification.request.content.data as Record<string, unknown>);
    });
    return () => sub.remove();
  }, [router, token]);

  return null;
}

import { useEffect, type Dispatch, type SetStateAction } from "react";

import { api, type User } from "@/lib/api";

type Options = {
  token: string | null;
  user: User | null;
  setUser: Dispatch<SetStateAction<User | null>>;
};

/** Post-login side effects — timezone, location, Gmail/push sync, RevenueCat, reminders. */
export function useBootstrapSync({ token, user, setUser }: Options): void {
  useEffect(() => {
    if (!token || !user) return;
    void import("@/lib/deviceTimezone").then(({ getDeviceTimezone }) => {
      const deviceTz = getDeviceTimezone();
      if (user.timezone !== deviceTz) {
        void api
          .updateMe(token, { timezone: deviceTz })
          .then((updated) => {
            // Only apply the fields this call changed — a full User replace
            // can race with an optimistic models/prefs patch and flash old toggles.
            setUser((current) =>
              current
                ? { ...current, timezone: updated.timezone }
                : updated,
            );
          })
          .catch(() => {});
      }
    });
  }, [token, user?.id, user?.timezone, setUser]);

  useEffect(() => {
    if (!token || !user?.location_enabled) return;
    void import("@/lib/deviceLocation").then(async ({ getDeviceLocationLabel }) => {
      const label = await getDeviceLocationLabel();
      if (label && user.location !== label) {
        void api
          .updateMe(token, { location: label })
          .then((updated) => {
            setUser((current) =>
              current
                ? { ...current, location: updated.location }
                : updated,
            );
          })
          .catch(() => {});
      }
    });
  }, [token, user?.id, user?.location, user?.location_enabled, setUser]);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    let cleanup: (() => void) | undefined;
    void import("@/lib/gmailAutoSync").then(({ attachGmailForegroundSync }) => {
      if (cancelled) return;
      cleanup = attachGmailForegroundSync(token);
    });
    return () => {
      cancelled = true;
      cleanup?.();
    };
  }, [token]);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    let cleanup: (() => void) | undefined;
    void import("@/lib/pushNotifications").then(({ attachPushForegroundSync }) => {
      if (cancelled) return;
      // Gate push registration on user.push_notifications_enabled — without
      // this, the backend holds a live push token for a user who opted out
      // and keeps sending them notifications. When disabled, the sync
      // unregisters the token instead of registering it.
      cleanup = attachPushForegroundSync(
        token,
        user?.push_notifications_enabled ?? false,
      );
    });
    return () => {
      cancelled = true;
      cleanup?.();
    };
  }, [token, user?.push_notifications_enabled]);

  useEffect(() => {
    if (user?.reminder_lead_minutes == null) return;
    void import("@/lib/reminderPrefs").then(({ syncReminderLeadFromServer }) =>
      syncReminderLeadFromServer(user.reminder_lead_minutes),
    );
  }, [user?.reminder_lead_minutes]);

  useEffect(() => {
    if (!token || !user?.id) return;
    let cancelled = false;
    let cleanup: (() => void) | undefined;
    void import("@/lib/purchases").then(
      async ({
        configurePurchases,
        isPurchasesConfigured,
        registerPlanChangeListener,
      }) => {
        if (cancelled) return;
        if (!isPurchasesConfigured()) return;
        await configurePurchases(user.id);
        if (cancelled) return;
        // Keep the backend plan in sync when the entitlement changes
        // (purchase / restore / expiry). The webhook may fail or lag; this
        // listener closes the gap without relying on a manual sync. The REST
        // call auto-refreshes the access token on 401, so a stale token is
        // fine.
        cleanup =
          (await registerPlanChangeListener(() => {
            void api.syncSubscription(token).then(setUser).catch(() => {});
          })) ?? undefined;
        if (cancelled) {
          cleanup?.();
          cleanup = undefined;
        }
      },
    );
    return () => {
      cancelled = true;
      cleanup?.();
    };
  }, [token, user?.id, setUser]);
}

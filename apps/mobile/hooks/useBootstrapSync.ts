import { useEffect, type Dispatch, type SetStateAction } from "react";

import { getDeviceTimezone } from "@/lib/deviceTimezone";
import { getDeviceLocationLabel } from "@/lib/deviceLocation";
import { configurePurchases, isPurchasesConfigured, registerPlanChangeListener } from "@/lib/purchases";
import { getSessionGeneration } from "@/lib/auth";
import { api, type User } from "@/lib/api";

type Options = {
  token: string | null;
  user: User | null;
  setUser: Dispatch<SetStateAction<User | null>>;
};

/** Post-login side effects — timezone, location, Gmail/push sync, RevenueCat, reminders. */
export function useBootstrapSync({ token, user, setUser }: Options): void {
  const userId = user?.id;
  const timezone = user?.timezone;
  const location = user?.location;
  const locationEnabled = user?.location_enabled;
  const pushEnabled = user?.push_notifications_enabled ?? false;
  const reminderLeadMinutes = user?.reminder_lead_minutes;
  useEffect(() => {
    if (!token || !userId) return;
    const generation = getSessionGeneration();
    let cancelled = false;
    const active = () => !cancelled && generation === getSessionGeneration();
    void (async () => {
      if (!active()) return;
      const deviceTz = getDeviceTimezone();
      if (timezone === deviceTz) return;
      const updated = await api.updateMe(token, { timezone: deviceTz });
      if (!active()) return;
      setUser((current) => current?.id === userId
        ? { ...current, timezone: updated.timezone } : current);
    })().catch(() => {
      if (active()) console.warn("[bootstrap] timezone sync failed");
    });
    return () => { cancelled = true; };
  }, [token, userId, timezone, setUser]);

  useEffect(() => {
    if (!token || !userId || !locationEnabled) return;
    const generation = getSessionGeneration();
    let cancelled = false;
    const active = () => !cancelled && generation === getSessionGeneration();
    void (async () => {
      if (!active()) return;
      const label = await getDeviceLocationLabel();
      if (!active() || !label || location === label) return;
      const updated = await api.updateMe(token, { location: label });
      if (!active()) return;
      setUser((current) => current?.id === userId
        ? { ...current, location: updated.location } : current);
    })().catch(() => {
      if (active()) console.warn("[bootstrap] location sync failed");
    });
    return () => { cancelled = true; };
  }, [token, userId, location, locationEnabled, setUser]);

  useEffect(() => {
    if (!token) return;
    const generation = getSessionGeneration();
    let cancelled = false;
    let cleanup: (() => void) | undefined;
    void import("@/lib/gmailAutoSync").then(({ attachGmailForegroundSync }) => {
      if (cancelled || generation !== getSessionGeneration()) return;
      cleanup = attachGmailForegroundSync(token);
    }).catch(() => {});
    return () => {
      cancelled = true;
      cleanup?.();
    };
  }, [token]);

  useEffect(() => {
    if (!token) return;
    const generation = getSessionGeneration();
    let cancelled = false;
    let cleanup: (() => void) | undefined;
    void import("@/lib/pushNotifications").then(({ attachPushForegroundSync }) => {
      if (cancelled || generation !== getSessionGeneration()) return;
      // Gate push registration on user.push_notifications_enabled — without
      // this, the backend holds a live push token for a user who opted out
      // and keeps sending them notifications. When disabled, the sync
      // unregisters the token instead of registering it.
      cleanup = attachPushForegroundSync(
        token,
        pushEnabled,
      );
    }).catch(() => {});
    return () => {
      cancelled = true;
      cleanup?.();
    };
  }, [token, pushEnabled]);

  useEffect(() => {
    if (reminderLeadMinutes == null) return;
    const generation = getSessionGeneration();
    let cancelled = false;
    void import("@/lib/reminderPrefs").then(({ syncReminderLeadFromServer }) => {
      if (cancelled || generation !== getSessionGeneration()) return;
      return syncReminderLeadFromServer(reminderLeadMinutes);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [userId, reminderLeadMinutes]);

  useEffect(() => {
    if (!token || !userId) return;
    const generation = getSessionGeneration();
    let cancelled = false;
    const active = () => !cancelled && generation === getSessionGeneration();
    let cleanup: (() => void) | undefined;
    void (async () => {
      if (!active() || !isPurchasesConfigured()) return;
      await configurePurchases(userId);
      if (!active()) return;
      // Keep the backend plan in sync when the entitlement changes
      // (purchase / restore / expiry). The webhook may fail or lag; this
      // listener closes the gap without relying on a manual sync. The REST
      // call auto-refreshes the access token on 401, so a stale token is
      // fine.
      cleanup =
        (await registerPlanChangeListener(() => {
          if (!active()) return;
          // M3: merge only the plan field — setUser replaces the entire
          // user object and bypasses the generation guard in updateUser,
          // so a slow sync can overwrite an in-flight profile patch (e.g.
          // timezone toggle snaps back).
          void api
            .syncSubscription(token)
            .then((updated) => {
              if (!active()) return;
              setUser((prev) => prev?.id === userId
                ? { ...prev, plan: updated.plan } : prev);
            })
            .catch(() => {});
        })) ?? undefined;
      if (!active()) {
        cleanup?.();
        cleanup = undefined;
      }
    })().catch(() => {});
    return () => {
      cancelled = true;
      cleanup?.();
    };
  }, [token, userId, setUser]);
}

import { useEffect, type Dispatch, type SetStateAction } from "react";

import { api, type User } from "@/lib/api";
import { isExpoGo } from "@/lib/expoRuntime";

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
        void api.updateMe(token, { timezone: deviceTz }).then(setUser).catch(() => {});
      }
    });
  }, [token, user?.id, user?.timezone, setUser]);

  useEffect(() => {
    if (!token || !user || isExpoGo()) return;
    void import("@/lib/deviceLocation").then(async ({ getDeviceLocationLabel }) => {
      const label = await getDeviceLocationLabel();
      if (label && user.location !== label) {
        void api.updateMe(token, { location: label }).then(setUser).catch(() => {});
      }
    });
  }, [token, user?.id, user?.location, setUser]);

  useEffect(() => {
    if (!token) return;
    let cleanup: (() => void) | undefined;
    void import("@/lib/gmailAutoSync").then(({ attachGmailForegroundSync }) => {
      cleanup = attachGmailForegroundSync(token);
    });
    return () => cleanup?.();
  }, [token]);

  useEffect(() => {
    if (!token) return;
    let cleanup: (() => void) | undefined;
    void import("@/lib/pushNotifications").then(({ attachPushForegroundSync }) => {
      cleanup = attachPushForegroundSync(token);
    });
    return () => cleanup?.();
  }, [token]);

  useEffect(() => {
    if (user?.reminder_lead_minutes == null) return;
    void import("@/lib/reminderPrefs").then(({ syncReminderLeadFromServer }) =>
      syncReminderLeadFromServer(user.reminder_lead_minutes),
    );
  }, [user?.reminder_lead_minutes]);

  useEffect(() => {
    if (!user?.id) return;
    void import("@/lib/purchases").then(({ configurePurchases, isPurchasesConfigured }) => {
      if (!isPurchasesConfigured()) return;
      void configurePurchases(user.id);
    });
  }, [user?.id]);
}

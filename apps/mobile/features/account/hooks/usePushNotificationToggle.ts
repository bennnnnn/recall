import { useCallback, useEffect, useRef, useState } from "react";

import { getSessionGeneration } from "@/lib/auth";
import { useOnForeground } from "@/lib/foregroundRefresh";
import {
  askNotificationPermission,
  getNotificationPermissionGranted,
  registerRemotePushToken,
  unregisterRemotePushToken,
} from "@/features/notifications/model/pushNotifications";

type PushNotificationToggleOptions = {
  token: string | null;
  serverEnabled: boolean;
  isCurrentView: () => boolean;
  updatePreference: (enabled: boolean) => Promise<void>;
  acquireMutation: () => (() => void) | null;
  onPermissionDenied: () => void;
  onError: () => void;
};

/**
 * Owns the push switch's optimistic draft without letting a stale screen or
 * previous account update the current view.
 */
export function usePushNotificationToggle({
  token,
  serverEnabled,
  isCurrentView,
  updatePreference,
  acquireMutation,
  onPermissionDenied,
  onError,
}: PushNotificationToggleOptions) {
  const session = getSessionGeneration();
  const [permissionGranted, setPermissionGranted] = useState<boolean | null>(null);
  const [optimisticValue, setOptimisticValue] = useState<boolean | null>(null);

  const sameAccount = useCallback(
    () => Boolean(token) && session === getSessionGeneration(),
    [session, token],
  );
  const isCurrent = useCallback(
    () => isCurrentView() && sameAccount(),
    [isCurrentView, sameAccount],
  );

  // The phone's permission, read when the page opens and on each return to the app: allowed
  // or taken away in the phone's Settings meanwhile, the switch shows it.
  const readPermission = useCallback((active: () => boolean = () => true) => {
    void getNotificationPermissionGranted()
      .then((granted) => {
        if (active() && isCurrent()) setPermissionGranted(granted);
      })
      .catch(() => {
        if (!active() || !isCurrent()) return;
        setPermissionGranted(false);
        onError();
      });
  }, [isCurrent, onError]);

  useEffect(() => {
    if (!isCurrent()) return;
    let active = true;
    readPermission(() => active);
    return () => {
      active = false;
    };
  }, [isCurrent, readPermission]);

  const value = optimisticValue ?? (serverEnabled && permissionGranted === true);

  /** The switch was turned on and the phone refused: allowed later, it finishes turning on. */
  const wantedOn = useRef(false);

  // The switch shows off, and the account's switch stays as it was: allowing notifications
  // later in the phone's Settings brings reminders back on the next return to the app.
  const setDenied = useCallback(() => {
    if (!isCurrent()) return;
    wantedOn.current = true;
    setPermissionGranted(false);
    setOptimisticValue(false);
    onPermissionDenied();
  }, [isCurrent, onPermissionDenied]);

  const toggle = useCallback(async (enabled: boolean) => {
    if (!token || !isCurrent()) return;
    const release = acquireMutation();
    if (!release) return;
    setOptimisticValue(enabled);

    wantedOn.current = false;
    try {
      if (!enabled) {
        await updatePreference(false);
        if (sameAccount()) await unregisterRemotePushToken(token);
        return;
      }

      // Recall says why, then the phone asks. Not now to Recall only puts the switch back.
      const answer = await askNotificationPermission();
      if (!sameAccount() || answer === "not_now") return;
      if (answer === "denied") {
        setDenied();
        return;
      }

      if (isCurrent()) setPermissionGranted(true);
      const registration = await registerRemotePushToken(token, true);
      if (!sameAccount()) return;
      if (registration === "no_permission") {
        setDenied();
        return;
      }
      await updatePreference(true);
    } catch {
      if (isCurrent()) onError();
    } finally {
      if (isCurrent()) setOptimisticValue(null);
      release();
    }
  }, [
    acquireMutation,
    isCurrent,
    onError,
    sameAccount,
    setDenied,
    token,
    updatePreference,
  ]);

  // Back from the phone's Settings: the switch shows the permission as it now is. One the
  // user turned on and the phone refused finishes turning on once it is allowed (no ask: it
  // is granted, so the token registers and the account's switch saves). A permission taken
  // away shows off and leaves the account's switch alone.
  useOnForeground(() => {
    if (!isCurrent()) return;
    if (!wantedOn.current) return readPermission();
    void getNotificationPermissionGranted().then((granted) => {
      if (!isCurrent()) return;
      setPermissionGranted(granted);
      if (granted && wantedOn.current) void toggle(true);
    }).catch(() => {});
  }, Boolean(token));

  return { value, permissionGranted, toggle };
}

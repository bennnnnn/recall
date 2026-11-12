import { useEffect, type Dispatch, type RefObject, type SetStateAction } from "react";

import { getSessionGeneration } from "@/lib/auth";
import { api, type User } from "@/lib/api";
import { getDeviceLocationLabel, locationAccessDenied } from "@/lib/deviceLocation";
import { FOREGROUND_STALE_MS, onAppStateChange } from "@/lib/foregroundRefresh";
import { recentSyncAt, recordSync } from "@/lib/syncRecords";

type Options = {
  signedIn: boolean;
  userId: string | undefined;
  location: string | null | undefined;
  locationEnabled: boolean | null | undefined;
  tokenRef: RefObject<string | null>;
  setUser: Dispatch<SetStateAction<User | null>>;
};

/**
 * The account's saved place, kept the phone's while Location is on: at sign-in and on each
 * return to the app, read again once it is an hour old (a GPS fix and a reverse geocode)
 * and saved even when unchanged, since the server dates the place it answers from. A turn
 * with no fix of its own reads that place; once a day old it answers nothing (review,
 * 2026-11-09: a place saved in San Francisco answered the weather in New York).
 * Location turned off in iOS Settings clears the saved place and leaves the switch the
 * user's (#1058): the next location question asks again.
 */
export function useLocationSync({ signedIn, userId, location, locationEnabled, tokenRef, setUser }: Options): void {
  useEffect(() => {
    if (!signedIn || !userId || !locationEnabled) return;
    const generation = getSessionGeneration();
    let cancelled = false;
    let running = false;
    const active = () => !cancelled && generation === getSessionGeneration();
    const save = async (place: string | null) => {
      const token = tokenRef.current;
      if (!token) return;
      const updated = await api.updateMe(token, { location: place });
      // Recorded before the new place re-runs this effect, so that run finds it.
      if (place) await recordSync("location", userId);
      if (!active()) return;
      setUser((latest) => latest?.id === userId ? { ...latest, location: updated.location } : latest);
    };
    const sync = async () => {
      if (running || !active()) return;
      running = true;
      try {
        const [denied, recent] = await Promise.all([
          locationAccessDenied(),
          location ? recentSyncAt("location", userId, FOREGROUND_STALE_MS.location) : null,
        ]);
        if (denied) {
          if (location && active()) await save(null);
          return;
        }
        // The server keeps the place between reads; without one, read it now.
        if (recent !== null) return;
        // On app open nothing asks: no permission sheet and no settings dialog.
        const place = await getDeviceLocationLabel({ ask: false });
        if (place && active()) await save(place);
      } finally {
        running = false;
      }
    };
    const report = () => {
      sync().catch(() => {
        if (active()) console.warn("[bootstrap] location sync failed");
      });
    };
    report();
    const stopForeground = onAppStateChange((_state, returned) => {
      if (returned) report();
    });
    return () => {
      cancelled = true;
      stopForeground();
    };
  }, [signedIn, userId, location, locationEnabled, setUser, tokenRef]);
}

import { useCallback, useEffect, useLayoutEffect, useRef, type MutableRefObject } from "react";

import type { RereadProfile } from "@/contexts/profileReread";
import { api, type User } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { FOREGROUND_STALE_MS, useOnForeground } from "@/lib/foregroundRefresh";
import { onReconnect } from "@/lib/reconnectRefresh";
import { zoneReportSettled } from "@/lib/zoneReport";

type Options = {
  /** Signed in: keyed on the account, never the token (NET-11). */
  signedIn: boolean;
  tokenRef: MutableRefObject<string | null>;
  userRef: MutableRefObject<User | null>;
  /** Bumped by every local change to the user (`updateUser`, `mergeUser`). */
  revisionRef: MutableRefObject<number>;
  isCurrent: (generation: number) => boolean;
  setCurrentUser: (next: User) => void;
  setProfileValidated: (validated: boolean) => void;
};

type ProfileReread = {
  reread: RereadProfile;
  /** The server just gave this phone the whole user (a launch, sign-in, refresh or save's answer):
   * marks it validated and read now, so no re-read follows within the window. */
  markRead: () => void;
  /** When `markRead` last ran. */
  readAtRef: MutableRefObject<number | null>;
  /** `updateUser` saves not yet answered: none is read over (contexts/useUpdateUser.ts). */
  savesWaitingRef: MutableRefObject<number>;
};

function isFresh(at: number | null, now: number, maxAgeMs: number): boolean {
  if (at == null) return false;
  // A clock set back makes the age negative: not fresh.
  const age = now - at;
  return age >= 0 && age < maxAgeMs;
}

/**
 * The signed-in user was read only at launch, so a change made anywhere else (a setting
 * on another device, a plan the store renewed or ended, a setting a chat message changed)
 * showed only after a restart, and every Settings row read the old one. This reads it again
 * on a return to the foreground and when a Settings page gains focus, at most once per
 * `maxAgeMs` (any answer with the whole user counts as a read; /auth/me sends no ETag).
 *
 * It never overwrites a local edit: with a save waiting it does not read (the save's answer
 * is the newer read), and an answer that lands after any change to the user here (a save,
 * a merge, the zone or the place sent, a token refresh's account) is dropped. The zone report
 * a return starts lands first, so the read never carries the old zone. An answer equal to
 * what is shown changes nothing on screen (no re-render, no cache write).
 */
export function useProfileReread({
  signedIn,
  tokenRef,
  userRef,
  revisionRef,
  isCurrent,
  setCurrentUser,
  setProfileValidated,
}: Options): ProfileReread {
  const readAtRef = useRef<number | null>(null);
  const savesWaitingRef = useRef(0);
  const flight = useRef<Promise<void> | null>(null);
  // A try that failed (offline) counts too: a Settings hop while offline sends nothing more.
  const triedAt = useRef<number | null>(null);
  /** The API came back while a read was still out (one started during the outage, which may yet
   * fail): when it ends without confirming the profile, it is read once more. */
  const readAgain = useRef(false);
  const rereadRef = useRef<(maxAgeMs: number) => void>(() => {});
  const markRead = useCallback(() => {
    readAtRef.current = Date.now();
    setProfileValidated(true);
  }, [setProfileValidated]);
  const reread = useCallback((maxAgeMs: number) => {
    const now = Date.now();
    if (flight.current || isFresh(readAtRef.current, now, maxAgeMs) || isFresh(triedAt.current, now, maxAgeMs)) return;
    if (!tokenRef.current || !userRef.current) return;
    const generation = getSessionGeneration();
    triedAt.current = now;
    flight.current = (async () => {
      try {
        await zoneReportSettled();
        const token = tokenRef.current;
        const before = userRef.current;
        if (!token || !before || !isCurrent(generation) || savesWaitingRef.current > 0) return;
        const revision = revisionRef.current;
        const me = await api.me(token);
        const untouched = isCurrent(generation)
          && revision === revisionRef.current
          && savesWaitingRef.current === 0
          && userRef.current === before
          && me.id === before.id;
        if (!untouched) return;
        markRead();
        if (JSON.stringify(me) === JSON.stringify(before)) return;
        setCurrentUser(me);
      } catch {
        // Best effort: the next return or Settings visit reads again.
        console.warn("[auth] could not read the profile again");
      } finally {
        flight.current = null;
        if (readAgain.current) {
          readAgain.current = false;
          if (readAtRef.current === null) rereadRef.current(0);
        }
      }
    })();
  }, [tokenRef, userRef, revisionRef, isCurrent, markRead, setCurrentUser]);
  useLayoutEffect(() => { rereadRef.current = reread; }, [reread]);
  useOnForeground(() => reread(FOREGROUND_STALE_MS.profile), signedIn);
  // Back after an outage (lib/reconnectRefresh.ts, what useReconnectRefresh runs for a screen;
  // this sits above the navigator, so it is not tied to a screen's focus): an offline launch
  // painted the cached account and its /auth/me failed, and nothing read it again until a
  // return from the background, so the profile stayed unconfirmed (no push or zone sync). Only
  // a profile the server has not confirmed this run is read: a confirmed one is read on the
  // usual returns, and every phone an outage refused need not ask for it again at once.
  useEffect(() => {
    if (!signedIn) return undefined;
    return onReconnect(() => {
      if (readAtRef.current !== null) return;
      // A read still out started while the API was down: it reads again if it fails.
      if (flight.current) readAgain.current = true;
      else reread(0);
    });
  }, [signedIn, reread]);
  return { reread, markRead, readAtRef, savesWaitingRef };
}

import { useCallback, useRef, useState, type MutableRefObject } from "react";

import { api, type User } from "@/lib/api";
import { emitAppEvent } from "@/lib/appEvents";
import { writeCachedUser } from "@/lib/cachedUser";

type Options = {
  token: string | null;
  sessionGeneration: number;
  profileValidated: boolean;
  isCurrent: (generation: number) => boolean;
  userRef: MutableRefObject<User | null>;
  /** Bumped by every change to the user here and by AuthContext's mergeUser: the latest wins. */
  revisionRef: MutableRefObject<number>;
  setCurrentUser: (next: User | null | ((previous: User | null) => User | null)) => void;
  setProfileValidated: (validated: boolean) => void;
};

/**
 * Runs tasks one after another, in the order they were given. A task starts once every
 * earlier one has settled, a failed one too; each caller gets its own task's result.
 */
function createSaveQueue() {
  let tail: Promise<unknown> = Promise.resolve();
  return {
    run<T>(task: () => Promise<T>): Promise<T> {
      const result = tail.then(task);
      tail = Promise.allSettled([result]);
      return result;
    },
  };
}

/**
 * AuthContext's `updateUser`: the patch shows at once (a switch moves when it is tapped),
 * then saves. Saves run one at a time, in the order they were made, so each answer is the
 * server after every earlier save: quick taps on two switches never land out of order, and
 * the last one shown is the one kept. A failed save puts the user back if no later change
 * has replaced it, and rejects, so no caller counts it as made (the owner's report of
 * switches that did not move, 2026-11-11).
 */
export function useUpdateUser({
  token,
  sessionGeneration,
  profileValidated,
  isCurrent,
  userRef,
  revisionRef,
  setCurrentUser,
  setProfileValidated,
}: Options): (patch: Partial<User>) => Promise<void> {
  const [queue] = useState(createSaveQueue);
  // What the server last said the user is: read when no save is waiting, then each answer.
  // A failed last save puts this back, never a snapshot holding an earlier save that failed.
  const confirmed = useRef<User | null>(null);
  const waiting = useRef(0);
  return useCallback((patch: Partial<User>) => {
    if (!token || !isCurrent(sessionGeneration)) return Promise.resolve();
    const revision = ++revisionRef.current;
    const snapshot = userRef.current;
    const snapshotValidated = profileValidated;
    if (waiting.current === 0) confirmed.current = snapshot;
    waiting.current += 1;
    setCurrentUser((previous) => previous ? { ...previous, ...patch } : previous);
    return queue.run(async () => {
      try {
        // Signed out while it waited: the next account's saves never queue behind it.
        if (!isCurrent(sessionGeneration)) throw new Error("signed out");
        const updated = await api.updateMe(token, patch);
        if (!isCurrent(sessionGeneration)) return;
        confirmed.current = updated;
        if (revision === revisionRef.current) {
          setCurrentUser(updated);
          setProfileValidated(true);
          void writeCachedUser(updated);
        }
        // Saved now, a later save waiting or not: what the server derives from these fields
        // (a to-do's notify_at, from quiet hours) may read again.
        const fields = (Object.keys(patch) as (keyof User)[]).filter((field) => snapshot?.[field] !== updated[field]);
        if (fields.length) emitAppEvent("userUpdated", { fields });
      } catch {
        const owns = isCurrent(sessionGeneration) && revision === revisionRef.current;
        if (owns) { setCurrentUser(confirmed.current ?? snapshot); setProfileValidated(snapshotValidated); }
        // Failed, whoever owns the user now: no caller may count this save as made.
        throw new Error("update failed");
      } finally {
        waiting.current -= 1;
      }
    });
  }, [token, sessionGeneration, profileValidated, isCurrent, userRef, revisionRef, setCurrentUser, setProfileValidated, queue]);
}

import { useEffect, type MutableRefObject } from "react";

import type { User } from "@/lib/api";
import { writeCachedUser } from "@/lib/cachedUser";

/**
 * The launch cache follows every change to the user the server has confirmed this run, by any
 * path: /auth/me, a sign-in, a save's answer, a re-read, a token refresh's account, the store's
 * plan sync. The next launch (an offline one too) paints the plan and settings as they were last
 * confirmed, never an older plan. `confirmed` is null before the server has said and after a
 * sign-out, so nothing is written back then. While a save is out (`savesWaitingRef`), the user on
 * screen holds its optimistic patch, which the server may refuse: it is not written, and the
 * save's answer or its rollback, which land after the count drops, is.
 */
export function useCachedUserWriter(
  confirmed: User | null,
  savesWaitingRef: MutableRefObject<number>,
): void {
  useEffect(() => {
    if (confirmed && savesWaitingRef.current === 0) void writeCachedUser(confirmed);
  }, [confirmed, savesWaitingRef]);
}

import { useEffect } from "react";

import type { User } from "@/lib/api";
import { writeCachedUser } from "@/lib/cachedUser";

/**
 * The launch cache follows every change to the user the server has confirmed this run, by any
 * path: /auth/me, a sign-in, a save, a re-read, a token refresh's account, the store's plan sync,
 * a merge. The next launch (an offline one too) paints the plan and settings as they were last
 * shown, never an older plan. `confirmed` is null before the server has said and after a
 * sign-out, so nothing is written back then.
 */
export function useCachedUserWriter(confirmed: User | null): void {
  useEffect(() => {
    if (confirmed) void writeCachedUser(confirmed);
  }, [confirmed]);
}

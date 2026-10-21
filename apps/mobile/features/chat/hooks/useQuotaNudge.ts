import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import { usageUsedPercent } from "@/lib/quota";

// Show the upgrade nudge once the free user has used this much of today's quota.
const QUOTA_NUDGE_THRESHOLD_PCT = 80;

// In-memory per-day dismissal. Resets when the app restarts — acceptable for a
// conversion nudge (it just re-shows once the next session of the same day).
// Avoids adding an AsyncStorage dependency for a non-sensitive UI flag.
let dismissedDate: string | null = null;

/** Sign-out: the next account sees the nudge on its own terms. */
export function resetQuotaNudgeDismissal(): void {
  dismissedDate = null;
}

function today(): string {
  // L7: use UTC (toISOString) to match the server's UTC-day quota reset.
  // A local-date slice would dismiss the nudge across a midnight boundary
  // that the server hasn't crossed yet.
  return new Date().toISOString().slice(0, 10);
}

type Options = {
  token: string | null;
  isPaid: boolean;
  /** The plan came from the server, not the launch cache (which says "free"). */
  planKnown: boolean;
  /** Bump to refetch (e.g. when a chat turn finishes and usage likely changed). */
  refreshKey: number;
};

/**
 * Fetches today's usage and decides whether to show a "you're nearing the free
 * limit, go Pro" nudge. Only fires for free users at/above the threshold, and
 * only once per day until dismissed. Pro users never see it, so their usage is
 * never fetched for it: the launch cache paints every plan as free, so this
 * waits for the server's word on the plan (`planKnown`).
 */
export function useQuotaNudge({ token, isPaid, planKnown, refreshKey }: Options) {
  const [show, setShow] = useState(false);
  const [usedPct, setUsedPct] = useState(0);
  // The hourly token rotation is not a reason to fetch usage again.
  const tokenRef = useRef(token);
  tokenRef.current = token;
  const signedIn = Boolean(token);

  useEffect(() => {
    const accessToken = tokenRef.current;
    if (!signedIn || !accessToken || isPaid || !planKnown) {
      setShow(false);
      return;
    }
    let cancelled = false;
    void (async () => {
      const usage = await api.todayUsage(accessToken).catch(() => null);
      if (cancelled || !usage) return;
      const pct = Math.round(usageUsedPercent(usage));
      setUsedPct(pct);
      if (pct >= QUOTA_NUDGE_THRESHOLD_PCT && dismissedDate !== today()) {
        setShow(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [signedIn, isPaid, planKnown, refreshKey]);

  const dismiss = useCallback(() => {
    dismissedDate = today();
    setShow(false);
  }, []);

  return { show, usedPct, dismiss };
}

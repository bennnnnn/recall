import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import { usageUsedPercent } from "@/lib/quota";

// Show the upgrade nudge once the free user has used this much of today's quota.
const QUOTA_NUDGE_THRESHOLD_PCT = 80;

// In-memory per-day dismissal. Resets when the app restarts — acceptable for a
// conversion nudge (it just re-shows once the next session of the same day).
// Avoids adding an AsyncStorage dependency for a non-sensitive UI flag.
let dismissedDate: string | null = null;

function today(): string {
  // L7: use UTC (toISOString) to match the server's UTC-day quota reset.
  // A local-date slice would dismiss the nudge across a midnight boundary
  // that the server hasn't crossed yet.
  return new Date().toISOString().slice(0, 10);
}

type Options = {
  token: string | null;
  isPaid: boolean;
  /** Bump to refetch (e.g. when a chat turn finishes and usage likely changed). */
  refreshKey: number;
};

/**
 * Fetches today's usage and decides whether to show a "you're nearing the free
 * limit, go Pro" nudge. Only fires for free users at/above the threshold, and
 * only once per day until dismissed. Pro users never see it.
 */
export function useQuotaNudge({ token, isPaid, refreshKey }: Options) {
  const [show, setShow] = useState(false);
  const [usedPct, setUsedPct] = useState(0);

  useEffect(() => {
    if (!token || isPaid) {
      setShow(false);
      return;
    }
    let cancelled = false;
    void (async () => {
      const usage = await api.todayUsage(token).catch(() => null);
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
  }, [token, isPaid, refreshKey]);

  const dismiss = useCallback(() => {
    dismissedDate = today();
    setShow(false);
  }, []);

  return { show, usedPct, dismiss };
}

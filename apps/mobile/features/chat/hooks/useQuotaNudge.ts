import { useCallback, useEffect, useState } from "react";

import { useAccountSession } from "@/contexts/accountSession";
import { api } from "@/lib/api";
import { usageUsedPercent } from "@/lib/quota";
import {
  dismissQuotaNudgeToday,
  quotaNudgeDismissedToday,
} from "@/features/chat/model/quotaNudgeDismissal";

// Show the upgrade nudge once the free user has used this much of today's quota.
const QUOTA_NUDGE_THRESHOLD_PCT = 80;

type Options = {
  isPaid: boolean;
  /** Bump to refetch (e.g. when a chat turn finishes and usage likely changed). */
  refreshKey: number;
};

/**
 * Fetches today's usage and decides whether to show a "you're nearing the free
 * limit, go Pro" nudge. Only fires for free users at/above the threshold, and
 * only once per day until dismissed. Pro users never see it.
 */
export function useQuotaNudge({ isPaid, refreshKey }: Options) {
  const { account, getToken } = useAccountSession();
  const [show, setShow] = useState(false);
  const [usedPct, setUsedPct] = useState(0);

  useEffect(() => {
    const token = getToken();
    if (!account || !token || isPaid) {
      setShow(false);
      return;
    }
    let cancelled = false;
    void (async () => {
      const usage = await api.todayUsage(token).catch(() => null);
      if (cancelled || !usage) return;
      const pct = Math.round(usageUsedPercent(usage));
      setUsedPct(pct);
      if (pct >= QUOTA_NUDGE_THRESHOLD_PCT && !quotaNudgeDismissedToday()) {
        setShow(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [account, getToken, isPaid, refreshKey]);

  const dismiss = useCallback(() => {
    dismissQuotaNudgeToday();
    setShow(false);
  }, []);

  return { show, usedPct, dismiss };
}

import { useCallback, useEffect, useState } from "react";

import { useAccountSession } from "@/contexts/accountSession";
import { fetchTodayUsage } from "@/lib/cache/usageCache";
import { usageUsedPercent } from "@/lib/quota";
import type { TurnUsage } from "@/features/chat/model/socketReduce";
import {
  dismissQuotaNudgeToday,
  quotaNudgeDismissedToday,
} from "@/features/chat/model/quotaNudgeDismissal";

// Show the upgrade nudge once the free user has used this much of today's quota.
const QUOTA_NUDGE_THRESHOLD_PCT = 80;

type Options = {
  isPaid: boolean;
};

/**
 * Decides whether to show a "you're nearing the free limit, go Pro" nudge. Only
 * fires for free users at/above the threshold, and only once per day until
 * dismissed. Pro users never see it.
 *
 * Today's usage is read once per account; after that each finished turn reports
 * the day's usage on its `done` (`applyTurnUsage`), so a turn costs no extra
 * request (code-health audit NET-14).
 */
export function useQuotaNudge({ isPaid }: Options) {
  const { account, getToken } = useAccountSession();
  const [show, setShow] = useState(false);
  const [usedPct, setUsedPct] = useState(0);

  const applyPercent = useCallback((pct: number) => {
    setUsedPct(pct);
    if (pct >= QUOTA_NUDGE_THRESHOLD_PCT && !quotaNudgeDismissedToday()) {
      setShow(true);
    }
  }, []);

  useEffect(() => {
    const token = getToken();
    if (!account || !token || isPaid) {
      setShow(false);
      return;
    }
    let cancelled = false;
    void (async () => {
      const usage = await fetchTodayUsage(account, token);
      if (cancelled || !usage) return;
      applyPercent(Math.round(usageUsedPercent(usage)));
    })();
    return () => {
      cancelled = true;
    };
  }, [account, getToken, isPaid, applyPercent]);

  const applyTurnUsage = useCallback(
    (usage: TurnUsage) => {
      if (!account || isPaid || usage.daily_limit <= 0) return;
      applyPercent(Math.round(Math.min(100, (usage.used_tokens / usage.daily_limit) * 100)));
    },
    [account, isPaid, applyPercent],
  );

  const dismiss = useCallback(() => {
    dismissQuotaNudgeToday();
    setShow(false);
  }, []);

  return { show, usedPct, dismiss, applyTurnUsage };
}

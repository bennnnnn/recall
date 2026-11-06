import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { useAccountSession } from "@/contexts/accountSession";
import { useAuthOptional } from "@/contexts/AuthContext";
import { fetchTodayUsage } from "@/lib/cache/usageCache";
import { usageMessages, usageUsedPercent } from "@/lib/quota";
import type { TurnUsage } from "@/features/chat/model/socketReduce";
import {
  dismissQuotaNudgeToday,
  quotaNudgeDismissedToday,
} from "@/features/chat/model/quotaNudgeDismissal";

// Show the upgrade nudge once the free user has used this much of today's quota.
const QUOTA_NUDGE_THRESHOLD_PCT = 80;

type Counted = { used: number; total: number };

/** The share of the day's messages used, 0 to 100. */
function percentOf(counted: Counted): number {
  return Math.round(Math.min(100, (counted.used / counted.total) * 100));
}

type Options = {
  isPaid: boolean;
};

/**
 * Decides whether to show a "you're nearing the free limit, go Pro" nudge. Only
 * fires for free users at/above the threshold, and only once per day until
 * dismissed. Pro users never see it, so their usage is never read for it: the
 * launch cache paints every plan as free, so this waits for the server's word on
 * the plan (`profileValidated`).
 *
 * Today's usage is read once per account; after that each finished turn reports
 * the day's usage on its `done` (`applyTurnUsage`), so a turn costs no extra
 * request (code-health audit NET-14).
 */
export function useQuotaNudge({ isPaid }: Options) {
  const { account, getToken } = useAccountSession();
  // A paid plan painted from the launch cache reads "free" until /auth/me answers.
  const planKnown = useAuthOptional()?.profileValidated ?? true;
  const { t } = useTranslation();
  const [show, setShow] = useState(false);
  const [usedPct, setUsedPct] = useState(0);
  // The day's messages when the server counts them: the banner says how many are left.
  const [messages, setMessages] = useState<Counted | null>(null);

  const applyPercent = useCallback((pct: number, counted: Counted | null = null) => {
    setUsedPct(pct);
    setMessages(counted);
    if (pct >= QUOTA_NUDGE_THRESHOLD_PCT && !quotaNudgeDismissedToday()) {
      setShow(true);
    }
  }, []);

  useEffect(() => {
    const token = getToken();
    if (!account || !token || isPaid || !planKnown) {
      setShow(false);
      return;
    }
    let cancelled = false;
    void (async () => {
      const usage = await fetchTodayUsage(account, token);
      if (cancelled || !usage) return;
      const counted = usageMessages(usage);
      applyPercent(counted ? percentOf(counted) : Math.round(usageUsedPercent(usage)), counted);
    })();
    return () => {
      cancelled = true;
    };
  }, [account, getToken, isPaid, planKnown, applyPercent]);

  const applyTurnUsage = useCallback(
    (usage: TurnUsage) => {
      if (!account || isPaid || !planKnown || usage.daily_limit <= 0) return;
      const counted = usage.daily_messages
        ? { used: Math.min(usage.daily_messages, usage.messages_used ?? 0), total: usage.daily_messages }
        : null;
      applyPercent(
        counted ? percentOf(counted) : Math.round(Math.min(100, (usage.used_tokens / usage.daily_limit) * 100)),
        counted,
      );
    },
    [account, isPaid, planKnown, applyPercent],
  );

  const dismiss = useCallback(() => {
    dismissQuotaNudgeToday();
    setShow(false);
  }, []);

  const label = messages
    ? t("chat.quota_nudge_messages", { left: messages.total - messages.used, total: messages.total })
    : t("chat.quota_nudge_body", { pct: usedPct });
  return { show, usedPct, label, dismiss, applyTurnUsage };
}

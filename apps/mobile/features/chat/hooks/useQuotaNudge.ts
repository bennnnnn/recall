import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { useAccountSession } from "@/contexts/accountSession";
import { useAuthOptional } from "@/contexts/AuthContext";
import { fetchTodayUsage } from "@/lib/cache/usageCache";
import { dayUsedPercent, usageMessages } from "@/lib/quota";
import type { TurnUsage } from "@/features/chat/model/socketReduce";
import {
  dismissQuotaNudgeToday,
  quotaNudgeDismissedToday,
} from "@/features/chat/model/quotaNudgeDismissal";
import { utcDayKey } from "@/lib/datetime/dayKey";

// Show the upgrade nudge once the free user has used this much of today's quota.
const QUOTA_NUDGE_THRESHOLD_PCT = 80;

type Counted = { used: number; total: number };

type Options = {
  isPaid: boolean;
  /** The chat's error: one for the day's messages turns Send off until tomorrow. */
  chatError?: { outOfMessages?: boolean } | null;
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
export function useQuotaNudge({ isPaid, chatError = null }: Options) {
  const { account, getToken } = useAccountSession();
  // A paid plan painted from the launch cache reads "free" until /auth/me answers.
  const planKnown = useAuthOptional()?.profileValidated ?? true;
  const { t } = useTranslation();
  const [show, setShow] = useState(false);
  const [usedPct, setUsedPct] = useState(0);
  // The day's messages when the server counts them: the banner says how many are left.
  const [dayCount, setDayCount] = useState<Counted | null>(null);
  // The server's UTC day on which Free ran out: Send is off until the next one.
  const [exhaustedDay, setExhaustedDay] = useState<string | null>(null);
  // Turns at each UTC midnight passed while out, so the day's usage is read again.
  const [dayTurn, setDayTurn] = useState(0);

  const applyPercent = useCallback((pct: number, counted: Counted | null = null) => {
    setUsedPct(pct);
    setDayCount(counted);
    if (counted && counted.used >= counted.total) setExhaustedDay(utcDayKey(new Date()));
    if (pct >= QUOTA_NUDGE_THRESHOLD_PCT && !quotaNudgeDismissedToday()) {
      setShow(true);
    }
  }, []);

  /** A send the server refused for the day's messages: the next one waits for tomorrow. */
  const markExhausted = useCallback(() => {
    setExhaustedDay(utcDayKey(new Date()));
    setDayCount((counted) => (counted ? { used: counted.total, total: counted.total } : counted));
  }, []);

  useEffect(() => {
    const token = getToken();
    if (!account || !token || isPaid || !planKnown) {
      setShow(false);
      setExhaustedDay(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      // After a midnight the cached count is yesterday's: read the new day's.
      const usage = dayTurn > 0 ? await fetchTodayUsage(account, token, { force: true }) : await fetchTodayUsage(account, token);
      if (cancelled || !usage) return;
      applyPercent(dayUsedPercent(usage), usageMessages(usage));
    })();
    return () => {
      cancelled = true;
    };
  }, [account, getToken, isPaid, planKnown, applyPercent, dayTurn]);

  // Out for the day: at the next UTC midnight Send comes back and the new day's count is read,
  // with the chat left open and nothing else re-rendering it.
  useEffect(() => {
    if (!exhaustedDay) return;
    const timer = setTimeout(() => {
      setExhaustedDay(null);
      setDayCount(null);
      setShow(false);
      setDayTurn((turn) => turn + 1);
    }, msToNextUtcDay(new Date()) + 1_000);
    return () => clearTimeout(timer);
  }, [exhaustedDay]);

  const applyTurnUsage = useCallback(
    (usage: TurnUsage) => {
      if (!account || isPaid || !planKnown || usage.daily_limit <= 0) return;
      applyPercent(dayUsedPercent(usage), usageMessages(usage));
    },
    [account, isPaid, planKnown, applyPercent],
  );

  // A send the server refused for the day's messages: Send waits for tomorrow from then on.
  const refusedForMessages = chatError?.outOfMessages === true;
  useEffect(() => {
    if (refusedForMessages) markExhausted();
  }, [refusedForMessages, markExhausted]);

  const dismiss = useCallback(() => {
    dismissQuotaNudgeToday();
    setShow(false);
  }, []);

  // Out for today (a free plan only): Send is off, and the banner stays to say why and offer
  // the plans, closed or not. The next UTC day turns it back on.
  const outOfMessages = !isPaid && planKnown && exhaustedDay === utcDayKey(new Date());
  const label = dayCount
    ? t("chat.quota_nudge_messages", { left: dayCount.total - dayCount.used, total: dayCount.total })
    : outOfMessages
      ? t("chat.quota_exceeded_free")
      : t("chat.quota_nudge_body", { pct: usedPct });
  return { show: show || outOfMessages, usedPct, label, dismiss, applyTurnUsage, outOfMessages, markExhausted };
}

/** Milliseconds from `now` to the next UTC midnight: when the server's day, and its count, turn. */
function msToNextUtcDay(now: Date): number {
  const next = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1);
  return next - now.getTime();
}

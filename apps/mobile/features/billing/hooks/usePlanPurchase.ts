import { useEffect, useState } from "react";

import { priceWithPeriod } from "@/features/billing/model/planCopy";
import { nextChargeDate } from "@/features/billing/model/planDates";
import {
  isPurchaseCancelled,
  type PlanPackage,
  purchasePlanPackage,
  restorePurchases,
} from "@/features/billing/model/purchases";
import { canRemindTrialEnd, remindBeforeTrialEnds } from "@/features/billing/model/trialReminder";
import type { Translate } from "@/lib/i18n/translate";
import type { PlanId } from "@/lib/plan";
import { trackProductEvent } from "@/lib/productAnalytics";
import { reportFailure } from "@/lib/sentry";

type Options = {
  token: string | null;
  /** A purchase the store holds for approval: none other is started meanwhile. */
  pending: unknown;
  /** The page promised the trial reminder (notifications can arrive): only then is it set. */
  canRemind: boolean;
  syncSubscription: () => Promise<unknown>;
  onClose: () => void;
  t: Translate;
};

/**
 * Buying and restoring on the plans page: one at a time, what went wrong said in words, and
 * the server told to read the store once it took the payment. A trial bought here gets the
 * reminder the page promised, a day before it ends.
 */
export function usePlanPurchase({ token, pending, canRemind, syncSubscription, onClose, t }: Options) {
  const [busy, setBusy] = useState<"buy" | "restore" | null>(null);
  const [error, setError] = useState<string | null>(null);

  /** The server reads the store again. The store took the payment, so a failure here says
   * "pending", never that it failed: the plan listener and the webhook still land it. */
  const syncAfterStore = async () => {
    if (!token) return;
    try {
      await syncSubscription();
      onClose();
    } catch (error) {
      reportFailure("purchase_sync", error);
      setError(t("upgrade.sync_pending"));
    }
  };

  const subscribe = async (pkg: PlanPackage) => {
    if (!token || busy || pending) return;
    const plan = pkg.plan;
    setBusy("buy");
    setError(null);
    trackProductEvent("purchase_started", { plan });
    let purchased: PlanId | "pending" = "free";
    try {
      purchased = await purchasePlanPackage(pkg);
    } catch (purchaseError) {
      const cancelled = isPurchaseCancelled(purchaseError);
      trackProductEvent("purchase_failed", { plan, reason: cancelled ? "cancelled" : "error" });
      if (!cancelled) reportFailure("purchase", purchaseError);
      if (!cancelled) setError(t("upgrade.purchase_failed"));
      setBusy(null);
      return;
    }
    // Neither bought nor failed: the store waits for approval, and the plan listener lands it.
    if (purchased === "pending") {
      setBusy(null);
      return;
    }
    if (purchased !== plan) {
      trackProductEvent("purchase_failed", { plan, reason: "error" });
      setError(t("upgrade.purchase_failed"));
      setBusy(null);
      return;
    }
    trackProductEvent("purchase_succeeded", { plan });
    await syncAfterStore();
    setBusy(null);
    // The page promised a reminder a day before the trial ends: set as the trial starts, after
    // the plan lands, so the notifications prompt it may show never holds the purchase up.
    if (pkg.trial && canRemind) {
      void remindBeforeTrialEnds(nextChargeDate(pkg.trial, pkg.period, new Date()), priceWithPeriod(pkg, t));
    }
  };

  const restore = async () => {
    if (!token || busy) return;
    setBusy("restore");
    setError(null);
    try {
      const restored = await restorePurchases();
      if (restored === "free") {
        setError(t("upgrade.restore_empty"));
        return;
      }
      await syncAfterStore();
    } catch (error) {
      reportFailure("purchase_restore", error);
      setError(t("upgrade.purchase_failed"));
    } finally {
      setBusy(null);
    }
  };

  return { busy, error, setError, subscribe, restore };
}

/** Whether the page may promise the trial reminder: read again each time it opens. */
export function useCanRemindTrialEnd(visible: boolean): boolean {
  const [canRemind, setCanRemind] = useState(false);
  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    void canRemindTrialEnd().then((can) => {
      if (!cancelled) setCanRemind(can);
    });
    return () => {
      cancelled = true;
    };
  }, [visible]);
  return canRemind;
}

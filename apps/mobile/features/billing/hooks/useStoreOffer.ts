import { useCallback, useEffect, useState, useSyncExternalStore } from "react";

import {
  getPlanPackages,
  isPurchasesConfigured,
  isStoreReady,
  type PlanOffer,
  recheckPendingPurchase,
  subscribeStoreReady,
} from "@/features/billing/model/purchases";
import { onAppStateChange } from "@/lib/foregroundRefresh";
import { reportFailure } from "@/lib/sentry";

const NO_OFFER: PlanOffer = { packages: {}, unavailable: false };
const STORE_NOT_SET_UP: PlanOffer = { packages: {}, unavailable: true };
/** How long the sheet waits for the store's set-up before saying the store is not answering. */
const STORE_SETUP_WAIT_MS = 8_000;
/**
 * The store's plans while the sheet shows. RevenueCat answers nothing before it is set up
 * for this account (after the server confirms the account and its plan), so the read waits
 * for that, the button spinning. A launch that never reached the server, or a set-up that
 * hung, leaves it waiting: after `STORE_SETUP_WAIT_MS` the store is said to be unavailable,
 * and Retry sets it up again (`setUpStore`).
 */
export function useStoreOffer(visible: boolean, setUpStore: () => Promise<void>) {
  const purchasesReady = isPurchasesConfigured();
  const storeReady = useSyncExternalStore(subscribeStoreReady, isStoreReady);
  const [offer, setOffer] = useState<PlanOffer>(NO_OFFER);
  const [attempt, setAttempt] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!visible || !purchasesReady) {
      setOffer(NO_OFFER);
      return;
    }
    setLoading(true);
    if (!storeReady) {
      const late = setTimeout(() => {
        setOffer(STORE_NOT_SET_UP);
        setLoading(false);
      }, STORE_SETUP_WAIT_MS);
      return () => clearTimeout(late);
    }
    let cancelled = false;
    void getPlanPackages()
      .then((next) => {
        if (!cancelled) setOffer(next);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [visible, purchasesReady, storeReady, attempt]);

  // A held purchase is read again as the sheet opens and as the app comes back.
  useEffect(() => {
    if (!visible) return;
    void recheckPendingPurchase();
    return onAppStateChange((_state, returned) => {
      if (returned) void recheckPendingPurchase();
    });
  }, [visible]);

  const retry = useCallback(() => {
    if (!isStoreReady()) {
      void setUpStore().catch((error: unknown) => reportFailure("paywall_load", error));
    }
    setAttempt((count) => count + 1);
  }, [setUpStore]);
  return { offer, loadingOffer: loading, purchasesReady, retry };
}

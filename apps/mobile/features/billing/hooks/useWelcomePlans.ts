import { useEffect, useRef, useSyncExternalStore } from "react";
import { AppState } from "react-native";

import { useAuthOptional } from "@/contexts/AuthContext";
import type { UpgradeSource } from "@/features/billing/components/UpgradeSheet";
import { isStoreReady, subscribeStoreReady } from "@/features/billing/model/purchases";
import {
  type OfferMoment,
  takeOutOfCreditOffer,
  takePlansOffer,
} from "@/features/billing/model/welcomePlans";
import { planOf } from "@/lib/plan";
import type { User } from "@/lib/api/types";

type Options = {
  user: User | null;
  /** A reply is being written: no offer covers it; its end is the "chatted" moment. */
  busy: boolean;
  /** Today's free allowance is used up, or the server refused a turn for it. */
  outOfCredit: boolean;
  open: (source: UpgradeSource) => void;
};

/**
 * Offers a free account the plans when one is due (`welcomePlans`): as the app opens or comes
 * back, after a reply, and when the day's allowance runs out. A paid account never sees it.
 *
 * The launch cache paints every plan "free" (`lib/cachedUser.ts`), so nothing is offered until
 * the server has said the plan, nor before the store can sell: RevenueCat answers no read
 * before it is set up for the account, and the sheet said "store unavailable".
 */
export function useWelcomePlans({ user, busy, outOfCredit, open }: Options) {
  const openRef = useRef(open);
  const busyRef = useRef(busy);
  const wasBusy = useRef(busy);
  const planKnown = useAuthOptional()?.profileValidated ?? false;
  const storeReady = useSyncExternalStore(subscribeStoreReady, isStoreReady);
  const free = planKnown && storeReady && user !== null && planOf(user) === "free";
  useEffect(() => {
    openRef.current = open;
    busyRef.current = busy;
  });

  const offerAt = useRef<(moment: OfferMoment) => void>(() => {});
  useEffect(() => {
    if (!free) {
      offerAt.current = () => {};
      return;
    }
    let live = true;
    offerAt.current = (moment) => {
      if (busyRef.current) return;
      void takePlansOffer(moment).then((offer) => {
        if (live && offer) openRef.current(offer);
      });
    };
    offerAt.current("open");
    const sub = AppState.addEventListener("change", (state) => {
      if (state === "active") offerAt.current("open");
    });
    return () => {
      live = false;
      sub.remove();
    };
  }, [free]);

  // A reply that just finished.
  useEffect(() => {
    if (wasBusy.current && !busy) offerAt.current("chatted");
    wasBusy.current = busy;
  }, [busy]);

  useEffect(() => {
    if (!free || !outOfCredit) return;
    let live = true;
    void takeOutOfCreditOffer().then((due) => {
      if (live && due) openRef.current("quota");
    });
    return () => {
      live = false;
    };
  }, [free, outOfCredit]);
}

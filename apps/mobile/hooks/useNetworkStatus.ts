import { useEffect, useRef, useState } from "react";
import { AppState, type AppStateStatus } from "react-native";
import NetInfo, { type NetInfoState } from "@react-native-community/netinfo";

import { isNetworkOffline } from "@/lib/networkStatus";
import { resolveIsOffline } from "@/lib/networkProbe";

const OFFLINE_POLL_MS = 1_500;

export function useNetworkStatus(): { isOffline: boolean } {
  const [isOffline, setIsOffline] = useState(false);
  // Bump to ignore in-flight probes after unmount or a newer event.
  const probeGen = useRef(0);

  useEffect(() => {
    const runProbe = () => {
      const gen = ++probeGen.current;
      void resolveIsOffline().then((offline) => {
        if (gen !== probeGen.current) return;
        setIsOffline(offline);
      });
    };

    const onNetInfo = (state: NetInfoState) => {
      // Online from NetInfo is trustworthy — clear immediately (no fetch).
      if (!isNetworkOffline(state)) {
        probeGen.current += 1;
        setIsOffline(false);
        return;
      }
      // Offline from NetInfo is often stale after reconnect (iOS/simulator).
      // Never flip the banner on from a raw event — confirm via probe.
      runProbe();
    };

    void NetInfo.fetch().then(onNetInfo);
    const unsubscribe = NetInfo.addEventListener(onNetInfo);

    const onAppState = (next: AppStateStatus) => {
      if (next === "active") runProbe();
    };
    const appSub = AppState.addEventListener("change", onAppState);

    return () => {
      probeGen.current += 1;
      unsubscribe();
      appSub.remove();
    };
  }, []);

  // While the banner is up, keep probing so a reconnect clears it even when
  // NetInfo never emits an "online" event.
  useEffect(() => {
    if (!isOffline) return;
    let cancelled = false;
    const tick = async () => {
      const offline = await resolveIsOffline();
      if (!cancelled) setIsOffline(offline);
    };
    void tick();
    const id = setInterval(() => void tick(), OFFLINE_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [isOffline]);

  return { isOffline };
}

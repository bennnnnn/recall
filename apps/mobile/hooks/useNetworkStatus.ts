import { useEffect, useRef, useState } from "react";
import { AppState, type AppStateStatus } from "react-native";
import NetInfo, { type NetInfoState } from "@react-native-community/netinfo";

import { isNetworkOffline } from "@/lib/networkStatus";
import {
  resolveConnectivity,
  type ConnectivityStatus,
} from "@/lib/networkProbe";

const OFFLINE_POLL_MS = 1_500;

export function useNetworkStatus(): {
  isOffline: boolean;
  status: ConnectivityStatus;
} {
  const [status, setStatus] = useState<ConnectivityStatus>("online");
  // Bump to ignore in-flight probes after unmount or a newer event.
  const probeGen = useRef(0);

  useEffect(() => {
    const runProbe = () => {
      const gen = ++probeGen.current;
      void resolveConnectivity().then((next) => {
        if (gen !== probeGen.current) return;
        setStatus(next);
      });
    };

    const onNetInfo = (state: NetInfoState) => {
      // Link up: drop a stale "No internet" banner immediately (iOS often
      // leaves isInternetReachable stuck false). Still probe — connected
      // Wi-Fi can be a captive portal or the API can be down.
      if (!isNetworkOffline(state)) {
        setStatus((prev) => (prev === "no_internet" ? "online" : prev));
        runProbe();
        return;
      }
      // Offline from NetInfo is often stale after reconnect. Never flip
      // no_internet on from a raw event — confirm via probe.
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

  // While degraded, keep probing so a reconnect clears the banner even when
  // NetInfo never emits an "online" event.
  useEffect(() => {
    if (status === "online") return;
    let cancelled = false;
    let probeInFlight = false;
    const tick = async () => {
      if (probeInFlight) return;
      probeInFlight = true;
      try {
        const next = await resolveConnectivity();
        if (!cancelled) setStatus(next);
      } finally {
        probeInFlight = false;
      }
    };
    void tick();
    const id = setInterval(() => void tick(), OFFLINE_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [status]);

  return { isOffline: status !== "online", status };
}

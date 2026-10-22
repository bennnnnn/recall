import { useCallback, useEffect, useRef, useState } from "react";
import { AppState, type AppStateStatus } from "react-native";
import NetInfo, { type NetInfoState } from "@react-native-community/netinfo";

import { isNetworkOffline } from "@/lib/networkStatus";
import {
  configureNetInfo,
  resolveConnectivity,
  type ConnectivityStatus,
} from "@/lib/networkProbe";

const FIRST_RETRY_MS = 1_500;
const MAX_RETRY_MS = 60_000;
const RETRY_JITTER = 0.2;

/**
 * The wait before degraded probe `attempt` (from 0): 1.5 s doubling to a minute, ±20%.
 * A fixed 1.5 s loop sent every foreground phone to /health 40 times a minute, in step,
 * for as long as the API looked down: just when it was recovering.
 */
export function retryDelayMs(attempt: number, random: () => number = Math.random): number {
  const base = Math.min(MAX_RETRY_MS, FIRST_RETRY_MS * 2 ** attempt);
  return Math.round(base * (1 - RETRY_JITTER + 2 * RETRY_JITTER * random()));
}

export function useNetworkStatus(): {
  isOffline: boolean;
  status: ConnectivityStatus;
} {
  const [status, setStatus] = useState<ConnectivityStatus>("online");
  // The degraded-state loop is for the banner on screen; it pauses in the
  // background and the return to "active" probes straight away.
  const [inBackground, setInBackground] = useState(false);
  // A link change or a return to the app starts the backoff over.
  const [retryEpoch, setRetryEpoch] = useState(0);
  // Bump to ignore in-flight probes after unmount or a newer event.
  const probeGen = useRef(0);
  // One probe at a time: start-up's fetch and the listener's first call, or an event
  // during the degraded loop, share the probe already on its way.
  const inFlight = useRef<Promise<ConnectivityStatus> | null>(null);
  const probe = useCallback((): Promise<ConnectivityStatus> => {
    inFlight.current ??= resolveConnectivity().finally(() => {
      inFlight.current = null;
    });
    return inFlight.current;
  }, []);

  useEffect(() => {
    configureNetInfo();
    const runProbe = () => {
      const gen = ++probeGen.current;
      void probe().then((next) => {
        if (gen !== probeGen.current) return;
        setStatus(next);
      });
    };

    const onNetInfo = (state: NetInfoState) => {
      setRetryEpoch((epoch) => epoch + 1);
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
      setInBackground(next === "background");
      if (next === "active") {
        setRetryEpoch((epoch) => epoch + 1);
        runProbe();
      }
    };
    const appSub = AppState.addEventListener("change", onAppState);

    return () => {
      probeGen.current += 1;
      unsubscribe();
      appSub.remove();
    };
  }, [probe]);

  // While degraded, keep probing so a reconnect clears the banner even when NetInfo
  // never emits an "online" event, backing off between probes.
  const degraded = status !== "online";
  useEffect(() => {
    if (!degraded || inBackground) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const waitThenProbe = (attempt: number) => {
      timer = setTimeout(() => {
        void probe().then((next) => {
          if (cancelled) return;
          setStatus(next);
          if (next !== "online") waitThenProbe(attempt + 1);
        });
      }, retryDelayMs(attempt));
    };
    waitThenProbe(0);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [degraded, inBackground, retryEpoch, probe]);

  return { isOffline: status !== "online", status };
}

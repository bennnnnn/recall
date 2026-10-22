import { useEffect, useMemo, useRef, useState } from "react";
import { AppState, type AppStateStatus } from "react-native";
import NetInfo, { type NetInfoState } from "@react-native-community/netinfo";

import { isNetworkOffline } from "@/lib/networkStatus";
import {
  resolveConnectivity,
  type ConnectivityStatus,
} from "@/lib/networkProbe";

const OFFLINE_POLL_MS = 1_500;

/**
 * The address the link has, where the OS gives it without extra permission
 * (Wi-Fi and Ethernet): a switch straight from one Wi-Fi network to another
 * is a new link, though its type stays "wifi".
 */
function linkAddress(state: NetInfoState): string {
  const details = state.details;
  const address = details && "ipAddress" in details ? details.ipAddress : null;
  return typeof address === "string" ? address : "";
}

export function useNetworkStatus(): {
  isOffline: boolean;
  status: ConnectivityStatus;
} {
  const [status, setStatus] = useState<ConnectivityStatus>("online");
  // The degraded-state loop is for the banner on screen; it pauses in the
  // background and the return to "active" probes straight away.
  const [inBackground, setInBackground] = useState(false);
  // Bump to ignore in-flight probes after unmount or a newer event.
  const probeGen = useRef(0);

  useEffect(() => {
    // The probe whose answer is still to come, if any.
    let pendingGen: number | null = null;
    // NetInfo repeats its report: once per subscription at launch, and again
    // after each probe's own refresh. Only a change of link, or the OS saying
    // the internet is unreachable, is news; its reachability check settling
    // to "reachable" just after launch is not.
    let lastLink: string | null = null;
    let lastOffline: boolean | null = null;

    /** Each probe is two requests; `join` lets one already running answer. */
    const runProbe = (join: boolean) => {
      if (join && pendingGen !== null) return;
      const gen = ++probeGen.current;
      pendingGen = gen;
      void resolveConnectivity().then((next) => {
        if (gen !== probeGen.current) return;
        pendingGen = null;
        setStatus(next);
      });
    };

    const onNetInfo = (state: NetInfoState) => {
      const offline = isNetworkOffline(state);
      const link = `${state.type}:${offline}:${state.isInternetReachable === false}:${linkAddress(state)}`;
      if (link === lastLink) return;
      // The link coming back up drops a stale "No internet" banner at once (iOS
      // often leaves isInternetReachable stuck false). A report on a link that
      // stayed up does not: on Wi-Fi with no internet behind it, the probe that
      // just found that triggers one. Offline from NetInfo is often stale after
      // reconnect, so it never flips the banner on by itself.
      const cameUp = lastOffline === true && !offline;
      lastLink = link;
      lastOffline = offline;
      if (cameUp) setStatus((prev) => (prev === "no_internet" ? "online" : prev));
      // Still probe a new link: connected Wi-Fi can be a captive portal or the
      // API can be down. A probe started on the old link is superseded.
      runProbe(false);
    };

    void NetInfo.fetch().then(onNetInfo);
    const unsubscribe = NetInfo.addEventListener(onNetInfo);

    const onAppState = (next: AppStateStatus) => {
      setInBackground(next === "background");
      if (next === "active") runProbe(true);
    };
    const appSub = AppState.addEventListener("change", onAppState);

    return () => {
      probeGen.current += 1;
      unsubscribe();
      appSub.remove();
    };
  }, []);

  // While degraded, keep probing so a reconnect clears the banner even when
  // NetInfo never emits an "online" event. Each probe is two requests.
  useEffect(() => {
    if (status === "online" || inBackground) return;
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
  }, [status, inBackground]);

  // Going to the background and back changes nothing a reader sees.
  return useMemo(() => ({ isOffline: status !== "online", status }), [status]);
}

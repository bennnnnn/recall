import { useEffect, useState } from "react";
import { AppState, type AppStateStatus } from "react-native";
import NetInfo, { type NetInfoState } from "@react-native-community/netinfo";

import { checkHealth } from "@/lib/api/connectivity";
import { isNetworkOffline } from "@/lib/networkStatus";

const OFFLINE_POLL_MS = 1_500;

export function useNetworkStatus(): { isOffline: boolean } {
  const [isOffline, setIsOffline] = useState(false);

  useEffect(() => {
    const apply = (state: NetInfoState) => {
      setIsOffline(isNetworkOffline(state));
    };

    const refresh = () => {
      void NetInfo.refresh().then(apply);
    };

    void NetInfo.fetch().then(apply);
    const unsubscribe = NetInfo.addEventListener(apply);

    const onAppState = (next: AppStateStatus) => {
      if (next === "active") refresh();
    };
    const appSub = AppState.addEventListener("change", onAppState);

    return () => {
      unsubscribe();
      appSub.remove();
    };
  }, []);

  // Simulator often misses reconnect events AND leaves NetInfo's
  // isConnected/isInternetReachable stale after reconnect — re-check while the
  // banner is visible, and confirm with a real /health ping so the banner
  // clears the moment the API is actually reachable again (not whenever NetInfo
  // gets around to updating).
  useEffect(() => {
    if (!isOffline) return;
    let cancelled = false;
    const refresh = async () => {
      // Cheap OS-level check first — catches a real reconnect without a fetch.
      const state = await NetInfo.refresh();
      if (cancelled) return;
      if (!isNetworkOffline(state)) {
        setIsOffline(false);
        return;
      }
      // NetInfo still says offline (often stale in the simulator) — confirm
      // with an actual /health request. If the API is reachable, we're online.
      if (await checkHealth()) {
        if (!cancelled) setIsOffline(false);
      }
    };
    void refresh();
    const id = setInterval(() => void refresh(), OFFLINE_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [isOffline]);

  return { isOffline };
}

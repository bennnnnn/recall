import { useEffect, useState } from "react";
import { AppState, type AppStateStatus } from "react-native";
import NetInfo, { type NetInfoState } from "@react-native-community/netinfo";

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

  // Simulator often misses reconnect events — re-check while banner is visible.
  useEffect(() => {
    if (!isOffline) return;
    const id = setInterval(refresh, OFFLINE_POLL_MS);
    function refresh() {
      void NetInfo.refresh().then((state) => {
        setIsOffline(isNetworkOffline(state));
      });
    }
    refresh();
    return () => clearInterval(id);
  }, [isOffline]);

  return { isOffline };
}

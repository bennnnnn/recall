import { useEffect, useState } from "react";
import NetInfo from "@react-native-community/netinfo";

import { isNetworkOffline } from "@/lib/networkStatus";

export function useNetworkStatus(): { isOffline: boolean } {
  const [isOffline, setIsOffline] = useState(false);

  useEffect(() => {
    const apply = (state: Parameters<typeof isNetworkOffline>[0]) => {
      setIsOffline(isNetworkOffline(state));
    };

    void NetInfo.fetch().then(apply);
    const unsubscribe = NetInfo.addEventListener(apply);
    return unsubscribe;
  }, []);

  return { isOffline };
}

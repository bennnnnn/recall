import { createContext, useContext, type ReactNode } from "react";

import { useNetworkStatus } from "@/hooks/useNetworkStatus";

type NetworkContextValue = { isOffline: boolean };

const NetworkContext = createContext<NetworkContextValue | null>(null);

export function NetworkProvider({ children }: { children: ReactNode }) {
  const { isOffline } = useNetworkStatus();
  return <NetworkContext.Provider value={{ isOffline }}>{children}</NetworkContext.Provider>;
}

export function useNetwork(): NetworkContextValue {
  const ctx = useContext(NetworkContext);
  // Fall back to "online" if used outside the provider rather than crashing screens.
  return ctx ?? { isOffline: false };
}

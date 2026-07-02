import type { NetInfoState } from "@react-native-community/netinfo";

/** True when the device has no usable internet (ignore unknown reachability on first tick). */
export function isNetworkOffline(state: NetInfoState): boolean {
  if (state.isConnected === false) return true;
  if (state.isInternetReachable === false) return true;
  return false;
}

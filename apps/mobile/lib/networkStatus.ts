import type { NetInfoState } from "@react-native-community/netinfo";

/**
 * Offline when the OS link is down, or reachability is unknown and reported bad.
 * When the link is up (isConnected === true), always online — iOS/simulator often
 * leaves isInternetReachable stuck false after reconnect.
 */
export function isNetworkOffline(state: NetInfoState): boolean {
  if (state.isConnected === true) return false;
  if (state.isConnected === false) return true;
  return state.isInternetReachable === false;
}

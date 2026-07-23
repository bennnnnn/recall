import NetInfo from "@react-native-community/netinfo";

import { checkHealth } from "@/lib/api/connectivity";
import { isNetworkOffline } from "@/lib/networkStatus";

/** Tiny captive-portal style check — proves the device has a working uplink
 * even when our API host is unreachable (wrong LAN IP, API down, etc.). */
const PUBLIC_REACHABILITY_URL = "https://clients3.google.com/generate_204";

export async function checkPublicReachability(timeoutMs = 3_000): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(PUBLIC_REACHABILITY_URL, {
      method: "GET",
      cache: "no-store",
      signal: controller.signal,
    });
    // 204 is the ideal response; some networks rewrite to 200/204/redirect.
    return res.status === 204 || res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * True only when OS link, API, and public reachability all look down.
 * Clears sticky "No internet" after reconnect when NetInfo is stale or the
 * API host is temporarily unreachable.
 */
export async function resolveIsOffline(): Promise<boolean> {
  const state = await NetInfo.refresh();
  if (!isNetworkOffline(state)) return false;
  if (await checkHealth()) return false;
  if (await checkPublicReachability()) return false;
  return true;
}

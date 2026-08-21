import NetInfo, { type NetInfoState } from "@react-native-community/netinfo";

import { checkHealth } from "@/lib/api/connectivity";
import { isNetworkOffline } from "@/lib/networkStatus";

/** Tiny captive-portal style check — proves the device has a working uplink
 * even when our API host is unreachable (wrong LAN IP, API down, etc.). */
const PUBLIC_REACHABILITY_URL = "https://clients3.google.com/generate_204";
const NETINFO_REFRESH_TIMEOUT_MS = 1_000;
const CONNECTIVITY_PROBE_TIMEOUT_MS = 3_500;

function settleWithin<T>(promise: Promise<T>, timeoutMs: number, fallback: T): Promise<T> {
  return new Promise((resolve) => {
    let settled = false;
    let timer: ReturnType<typeof setTimeout>;
    const finish = (value: T) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(value);
    };
    timer = setTimeout(() => finish(fallback), timeoutMs);
    void promise.then(finish, () => finish(fallback));
  });
}

function firstReachable(probes: Promise<boolean>[], timeoutMs: number): Promise<boolean> {
  return new Promise((resolve) => {
    let settled = false;
    let remaining = probes.length;
    const finish = (reachable: boolean) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(reachable);
    };
    const timer = setTimeout(() => finish(false), timeoutMs);
    for (const probe of probes) {
      void probe.then(
        (reachable) => {
          if (reachable) {
            finish(true);
            return;
          }
          remaining -= 1;
          if (remaining === 0) finish(false);
        },
        () => {
          remaining -= 1;
          if (remaining === 0) finish(false);
        }
      );
    }
  });
}

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
  // NetInfo.refresh can remain unresolved after an iOS/simulator reconnect.
  // Give it a short chance to report the restored link, then independently
  // verify the API and public internet in parallel.
  const state = await settleWithin<NetInfoState | null>(
    NetInfo.refresh(),
    NETINFO_REFRESH_TIMEOUT_MS,
    null,
  );
  if (state && !isNetworkOffline(state)) return false;

  const reachable = await firstReachable(
    [
      checkHealth(CONNECTIVITY_PROBE_TIMEOUT_MS),
      checkPublicReachability(CONNECTIVITY_PROBE_TIMEOUT_MS),
    ],
    CONNECTIVITY_PROBE_TIMEOUT_MS,
  );
  return !reachable;
}

import { api } from "@/lib/api";

export type IntegrationStatusSnapshot = {
  calendarConnected: boolean;
  gmailConnected: boolean;
};

let cache: IntegrationStatusSnapshot | null = null;
let inflight: Promise<IntegrationStatusSnapshot | null> | null = null;

export function getCachedIntegrationStatus(): IntegrationStatusSnapshot | null {
  return cache;
}

export function connectedCountFromStatus(status: IntegrationStatusSnapshot): number {
  return (status.calendarConnected ? 1 : 0) + (status.gmailConnected ? 1 : 0);
}

export function getCachedConnectedCount(): number {
  return cache ? connectedCountFromStatus(cache) : 0;
}

export function setIntegrationStatusCache(status: IntegrationStatusSnapshot): void {
  cache = status;
}

export function patchIntegrationStatusCache(
  patch: Partial<IntegrationStatusSnapshot>,
): void {
  cache = {
    calendarConnected: patch.calendarConnected ?? cache?.calendarConnected ?? false,
    gmailConnected: patch.gmailConnected ?? cache?.gmailConnected ?? false,
  };
}

export function invalidateIntegrationStatusCache(): void {
  cache = null;
  inflight = null;
}

/**
 * Hub screens reuse this snapshot so Settings focus does not refetch
 * calendar/Gmail status. Pass `{ force: true }` from the integrations
 * screen (the only place connection state actually changes).
 */
export async function fetchIntegrationStatus(
  token: string,
  opts?: { force?: boolean },
): Promise<IntegrationStatusSnapshot | null> {
  if (!opts?.force && cache) return cache;
  if (inflight) return inflight;

  const task = (async () => {
    try {
      const [calendarR, gmailR] = await Promise.allSettled([
        api.googleCalendarStatus(token),
        api.googleGmailStatus(token),
      ]);
      const next: IntegrationStatusSnapshot = {
        calendarConnected:
          calendarR.status === "fulfilled"
            ? calendarR.value.connected
            : (cache?.calendarConnected ?? false),
        gmailConnected:
          gmailR.status === "fulfilled"
            ? gmailR.value.connected
            : (cache?.gmailConnected ?? false),
      };
      if (calendarR.status === "fulfilled" || gmailR.status === "fulfilled") {
        cache = next;
        return next;
      }
      return cache;
    } finally {
      inflight = null;
    }
  })();

  inflight = task;
  return task;
}

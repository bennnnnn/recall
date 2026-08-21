import { api } from "@/lib/api";
import { StaleResourceCache } from "@/lib/cache/staleResource";

export type IntegrationStatusSnapshot = {
  calendarConnected: boolean;
  gmailConnected: boolean;
};

const INTEGRATION_STATUS_KEY = "integration-status";
const resource = new StaleResourceCache<string, IntegrationStatusSnapshot>(
  Number.POSITIVE_INFINITY,
);

export function getCachedIntegrationStatus(): IntegrationStatusSnapshot | null {
  return resource.get(INTEGRATION_STATUS_KEY) ?? null;
}

export function connectedCountFromStatus(status: IntegrationStatusSnapshot): number {
  return (status.calendarConnected ? 1 : 0) + (status.gmailConnected ? 1 : 0);
}

export function getCachedConnectedCount(): number {
  const cached = getCachedIntegrationStatus();
  return cached ? connectedCountFromStatus(cached) : 0;
}

export function setIntegrationStatusCache(status: IntegrationStatusSnapshot): void {
  resource.set(INTEGRATION_STATUS_KEY, status);
}

export function patchIntegrationStatusCache(
  patch: Partial<IntegrationStatusSnapshot>,
): void {
  resource.update(INTEGRATION_STATUS_KEY, (cached) => ({
    calendarConnected: patch.calendarConnected ?? cached?.calendarConnected ?? false,
    gmailConnected: patch.gmailConnected ?? cached?.gmailConnected ?? false,
  }));
}

export function invalidateIntegrationStatusCache(): void {
  resource.invalidate(INTEGRATION_STATUS_KEY);
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
  try {
    return await resource.fetch(
      INTEGRATION_STATUS_KEY,
      async () => {
      const cached = resource.get(INTEGRATION_STATUS_KEY);
      const [calendarR, gmailR] = await Promise.allSettled([
        api.googleCalendarStatus(token),
        api.googleGmailStatus(token),
      ]);
      const next: IntegrationStatusSnapshot = {
        calendarConnected:
          calendarR.status === "fulfilled"
            ? calendarR.value.connected
            : (cached?.calendarConnected ?? false),
        gmailConnected:
          gmailR.status === "fulfilled"
            ? gmailR.value.connected
            : (cached?.gmailConnected ?? false),
      };
      if (calendarR.status === "fulfilled" || gmailR.status === "fulfilled") {
        return next;
      }
      if (cached) return cached;
      throw new Error("Integration status unavailable");
      },
      opts,
    );
  } catch {
    return resource.get(INTEGRATION_STATUS_KEY) ?? null;
  }
}

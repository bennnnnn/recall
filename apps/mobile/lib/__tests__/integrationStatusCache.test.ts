import { api } from "@/lib/api";
import {
  connectedCountFromStatus,
  fetchIntegrationStatus,
  getCachedConnectedCount,
  getCachedIntegrationStatus,
  invalidateIntegrationStatusCache,
  patchIntegrationStatusCache,
  setIntegrationStatusCache,
} from "@/lib/cache/integrationStatusCache";

jest.mock("@/lib/api", () => ({
  api: {
    googleCalendarStatus: jest.fn(),
    googleGmailStatus: jest.fn(),
  },
}));

const googleCalendarStatus = api.googleCalendarStatus as jest.Mock;
const googleGmailStatus = api.googleGmailStatus as jest.Mock;

describe("integrationStatusCache", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    invalidateIntegrationStatusCache();
  });

  it("returns the cached snapshot without refetching", async () => {
    setIntegrationStatusCache({ calendarConnected: true, gmailConnected: false });
    expect(getCachedConnectedCount()).toBe(1);

    const result = await fetchIntegrationStatus("token");
    expect(result).toEqual({ calendarConnected: true, gmailConnected: false });
    expect(googleCalendarStatus).not.toHaveBeenCalled();
    expect(googleGmailStatus).not.toHaveBeenCalled();
  });

  it("fetches once when empty and caches the connected flags", async () => {
    googleCalendarStatus.mockResolvedValue({ connected: true, configured: true });
    googleGmailStatus.mockResolvedValue({ connected: true, configured: true });

    const result = await fetchIntegrationStatus("token");
    expect(result).toEqual({ calendarConnected: true, gmailConnected: true });
    expect(getCachedConnectedCount()).toBe(2);
    expect(googleCalendarStatus).toHaveBeenCalledTimes(1);
  });

  it("force refetch updates the cache", async () => {
    setIntegrationStatusCache({ calendarConnected: false, gmailConnected: false });
    googleCalendarStatus.mockResolvedValue({ connected: true, configured: true });
    googleGmailStatus.mockResolvedValue({ connected: false, configured: true });

    const result = await fetchIntegrationStatus("token", { force: true });
    expect(result).toEqual({ calendarConnected: true, gmailConnected: false });
    expect(getCachedIntegrationStatus()).toEqual(result);
  });

  it("patch updates one flag without dropping the other", () => {
    setIntegrationStatusCache({ calendarConnected: true, gmailConnected: false });
    patchIntegrationStatusCache({ gmailConnected: true });
    expect(getCachedIntegrationStatus()).toEqual({
      calendarConnected: true,
      gmailConnected: true,
    });
    expect(connectedCountFromStatus(getCachedIntegrationStatus()!)).toBe(2);
  });
});

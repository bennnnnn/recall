import { api } from "@/lib/api";
import { trackProductEvent } from "@/lib/productAnalytics";

jest.mock("@/lib/api", () => ({
  api: {
    recordProductEvents: jest.fn().mockResolvedValue(undefined),
  },
}));

jest.mock("@/lib/installationId", () => ({
  getInstallationId: jest.fn().mockResolvedValue("installation-1"),
}));

jest.mock("expo-constants", () => ({
  __esModule: true,
  default: {
    expoConfig: { version: "1.2.3" },
  },
}));

jest.mock("react-native", () => ({
  Platform: { OS: "ios" },
}));

const flushAnalytics = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

describe("trackProductEvent", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("sends only structured event metadata", async () => {
    trackProductEvent("token", "paywall_viewed", { source: "settings" });

    await flushAnalytics();
    expect(api.recordProductEvents).toHaveBeenCalledTimes(1);
    expect(api.recordProductEvents).toHaveBeenCalledWith(
      "token",
      expect.arrayContaining([
        expect.objectContaining({
          name: "paywall_viewed",
          properties: { source: "settings" },
          app_version: "1.2.3",
          installation_id: "installation-1",
        }),
      ]),
    );
  });

  it("does nothing before authentication", async () => {
    trackProductEvent(null, "purchase_started");
    await flushAnalytics();
    expect(api.recordProductEvents).not.toHaveBeenCalled();
  });

  it("swallows analytics delivery failures", async () => {
    (api.recordProductEvents as jest.Mock).mockRejectedValueOnce(new Error("offline"));
    expect(() => trackProductEvent("token", "purchase_started")).not.toThrow();
    await flushAnalytics();
    expect(api.recordProductEvents).toHaveBeenCalledTimes(1);
  });
});

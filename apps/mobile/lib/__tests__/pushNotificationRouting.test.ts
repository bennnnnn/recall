jest.mock("@/lib/api", () => ({
  api: {
    registerPushToken: jest.fn(),
    unregisterPushToken: jest.fn(),
    recordProductEvents: jest.fn(),
    updateMe: jest.fn(),
  },
}));

jest.mock("@/lib/installationId", () => ({
  getInstallationId: jest.fn().mockResolvedValue("dev-1"),
}));

jest.mock("expo-constants", () => ({
  __esModule: true,
  default: { expoConfig: { extra: { eas: { projectId: "p1" } } } },
}));

jest.mock("expo-notifications", () => ({
  getPermissionsAsync: jest.fn(),
  requestPermissionsAsync: jest.fn(),
  setNotificationChannelAsync: jest.fn(),
  getExpoPushTokenAsync: jest.fn(),
  setNotificationHandler: jest.fn(),
}));

jest.mock("react-native", () => ({
  Platform: { OS: "ios" },
  AppState: { addEventListener: () => ({ remove: jest.fn() }) },
}));

import { handlePushNotificationResponse } from "@/lib/pushNotifications";

function fakeRouter() {
  return { push: jest.fn(), replace: jest.fn() };
}

describe("handlePushNotificationResponse: job_search_ready", () => {
  it("opens the dedicated My Job dashboard", async () => {
    const router = fakeRouter();
    await handlePushNotificationResponse(router, "tok", {
      type: "job_search_ready",
      screen: "my-job",
      profile_id: "profile-1",
    });
    expect(router.push).toHaveBeenCalledWith("/my-job");
  });

  it("also routes on the dedicated screen value", async () => {
    const router = fakeRouter();
    await handlePushNotificationResponse(router, "tok", { screen: "my-job" });
    expect(router.push).toHaveBeenCalledWith("/my-job");
  });
});

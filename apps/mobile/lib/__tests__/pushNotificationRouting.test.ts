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

describe("handlePushNotificationResponse: automation_run", () => {
  it("opens the automation's detail screen when automation_id is present", async () => {
    const router = fakeRouter();
    await handlePushNotificationResponse(router, "tok", {
      type: "automation_run",
      screen: "automations",
      automation_id: "auto-1",
      chat_id: "chat-1",
    } as never);
    expect(router.push).toHaveBeenCalledWith("/automations/auto-1");
  });

  it("falls back to the Automations list when automation_id is missing", async () => {
    const router = fakeRouter();
    await handlePushNotificationResponse(router, "tok", { type: "automation_run" } as never);
    expect(router.push).toHaveBeenCalledWith("/automations");
  });

  it("also routes on screen=automations without the automation_run type", async () => {
    const router = fakeRouter();
    await handlePushNotificationResponse(router, "tok", {
      screen: "automations",
      automation_id: "auto-2",
    } as never);
    expect(router.push).toHaveBeenCalledWith("/automations/auto-2");
  });

  it("does not route automation_run through the reminders path", async () => {
    const router = fakeRouter();
    await handlePushNotificationResponse(router, "tok", {
      type: "automation_run",
      automation_id: "auto-3",
    } as never);
    expect(router.push).not.toHaveBeenCalledWith(
      expect.objectContaining({ pathname: "/todos" }),
    );
  });
});

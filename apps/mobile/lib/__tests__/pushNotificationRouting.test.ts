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
  it("opens the completed result conversation when chat_id is present", async () => {
    const router = fakeRouter();
    await handlePushNotificationResponse(router, "tok", {
      type: "automation_run",
      screen: "automations",
      automation_id: "auto-1",
      chat_id: "chat-1",
    });
    expect(router.push).toHaveBeenCalledWith({
      pathname: "/open-chat",
      params: { chatId: "chat-1" },
    });
  });

  it("falls back to automation detail when a result chat id is missing", async () => {
    const router = fakeRouter();
    await handlePushNotificationResponse(router, "tok", {
      type: "automation_run",
      automation_id: "auto-1",
    });
    expect(router.push).toHaveBeenCalledWith("/automations/auto-1");
  });

  it("falls back to the Automations list when all ids are missing", async () => {
    const router = fakeRouter();
    await handlePushNotificationResponse(router, "tok", { type: "automation_run" });
    expect(router.push).toHaveBeenCalledWith("/automations");
  });

  it("routes a generic screen=automations link to task detail", async () => {
    const router = fakeRouter();
    await handlePushNotificationResponse(router, "tok", {
      screen: "automations",
      automation_id: "auto-2",
    });
    expect(router.push).toHaveBeenCalledWith("/automations/auto-2");
  });

  it("does not route automation_run through the reminders path", async () => {
    const router = fakeRouter();
    await handlePushNotificationResponse(router, "tok", {
      type: "automation_run",
      automation_id: "auto-3",
    });
    expect(router.push).not.toHaveBeenCalledWith(
      expect.objectContaining({ pathname: "/todos" }),
    );
  });
});

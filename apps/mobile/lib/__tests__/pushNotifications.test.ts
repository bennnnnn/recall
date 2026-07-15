jest.mock("@/lib/api", () => ({
  api: {
    registerPushToken: jest.fn().mockResolvedValue(undefined),
    unregisterPushToken: jest.fn().mockResolvedValue(undefined),
  },
}));

jest.mock("expo-constants", () => ({
  __esModule: true,
  default: { installationId: "dev-1", expoConfig: { extra: { eas: { projectId: "p1" } } } },
}));

jest.mock("expo-notifications", () => ({
  getPermissionsAsync: jest.fn().mockResolvedValue({ status: "granted" }),
  requestPermissionsAsync: jest.fn().mockResolvedValue({ status: "granted" }),
  setNotificationChannelAsync: jest.fn().mockResolvedValue(undefined),
  getExpoPushTokenAsync: jest.fn().mockResolvedValue({ data: "ExponentPushToken[abc]" }),
  setNotificationHandler: jest.fn(),
}));

jest.mock("react-native", () => ({
  Platform: { OS: "ios" },
  AppState: { addEventListener: () => ({ remove: jest.fn() }) },
}));

import { Platform } from "react-native";

import { api } from "@/lib/api";
import {
  attachPushForegroundSync,
  registerRemotePushToken,
  unregisterRemotePushToken,
} from "@/lib/pushNotifications";

const registerMock = api.registerPushToken as jest.MockedFunction<typeof api.registerPushToken>;
const unregisterMock = api.unregisterPushToken as jest.MockedFunction<typeof api.unregisterPushToken>;

describe("push gating on user.push_notifications_enabled", () => {
  beforeEach(() => {
    Platform.OS = "ios";
    registerMock.mockClear();
    unregisterMock.mockClear();
  });

  it("registerRemotePushToken registers when pushNotificationsEnabled=true", async () => {
    await registerRemotePushToken("tok", true);
    expect(registerMock).toHaveBeenCalledTimes(1);
    expect(registerMock).toHaveBeenCalledWith(
      "tok",
      expect.objectContaining({ expo_push_token: "ExponentPushToken[abc]" }),
    );
  });

  it("registerRemotePushToken is a no-op when pushNotificationsEnabled=false", async () => {
    // Without this gate, the backend holds a live push token for a user who
    // opted out and keeps sending them notifications.
    await registerRemotePushToken("tok", false);
    expect(registerMock).not.toHaveBeenCalled();
  });

  it("unregisterRemotePushToken calls the server unregister endpoint", async () => {
    await unregisterRemotePushToken("tok");
    expect(unregisterMock).toHaveBeenCalledTimes(1);
    expect(unregisterMock).toHaveBeenCalledWith(
      "tok",
      expect.objectContaining({ expo_push_token: "ExponentPushToken[abc]" }),
    );
  });

  it("attachPushForegroundSync returns a cleanup function and does not throw", () => {
    // The register/unregister behaviour is covered by the direct tests above;
    // here we just verify the sync contract: returns a cleanup fn, no throw.
    const cleanupOn = attachPushForegroundSync("tok", true);
    expect(typeof cleanupOn).toBe("function");
    cleanupOn();

    const cleanupOff = attachPushForegroundSync("tok", false);
    expect(typeof cleanupOff).toBe("function");
    cleanupOff();
  });

  it("attachPushForegroundSync is a no-op when apiToken is null", () => {
    const cleanup = attachPushForegroundSync(null, true);
    expect(typeof cleanup).toBe("function");
    cleanup();
    expect(registerMock).not.toHaveBeenCalled();
    expect(unregisterMock).not.toHaveBeenCalled();
  });
});

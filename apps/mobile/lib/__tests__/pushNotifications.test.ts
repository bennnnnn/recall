jest.mock("@/lib/api", () => ({
  api: {
    registerPushToken: jest.fn().mockResolvedValue(undefined),
    unregisterPushToken: jest.fn().mockResolvedValue(undefined),
    recordProductEvents: jest.fn().mockResolvedValue(undefined),
    updateMe: jest.fn().mockResolvedValue({}),
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
  getPermissionsAsync: jest.fn().mockResolvedValue({ status: "granted" }),
  requestPermissionsAsync: jest.fn().mockResolvedValue({ status: "granted" }),
  setNotificationChannelAsync: jest.fn().mockResolvedValue(undefined),
  getExpoPushTokenAsync: jest.fn().mockResolvedValue({ data: "ExponentPushToken[abc]" }),
  setNotificationHandler: jest.fn(),
  AndroidImportance: { HIGH: 4, DEFAULT: 3 },
}));

const mockAppStateHandlers = new Set<(state: string) => void>();

jest.mock("react-native", () => ({
  Platform: { OS: "ios" },
  AppState: {
    addEventListener: (_event: string, handler: (state: string) => void) => {
      mockAppStateHandlers.add(handler);
      return { remove: jest.fn(() => mockAppStateHandlers.delete(handler)) };
    },
  },
}));

import { Platform } from "react-native";
import * as Notifications from "expo-notifications";

import { api } from "@/lib/api";
import {
  attachPushForegroundSync,
  ensureNotificationPermission,
  getNotificationPermissionGranted,
  registerRemotePushToken,
  unregisterRemotePushToken,
} from "@/lib/pushNotifications";

const registerMock = api.registerPushToken as jest.MockedFunction<typeof api.registerPushToken>;
const unregisterMock = api.unregisterPushToken as jest.MockedFunction<
  typeof api.unregisterPushToken
>;
const updateMeMock = api.updateMe as jest.MockedFunction<typeof api.updateMe>;

describe("push gating on user.push_notifications_enabled", () => {
  beforeEach(() => {
    Platform.OS = "ios";
    registerMock.mockClear();
    unregisterMock.mockClear();
    updateMeMock.mockClear();
    (api.recordProductEvents as jest.Mock).mockClear();
    (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: "granted" });
    (Notifications.requestPermissionsAsync as jest.Mock).mockReset();
    (Notifications.requestPermissionsAsync as jest.Mock).mockResolvedValue({ status: "granted" });
  });

  it("registerRemotePushToken registers when pushNotificationsEnabled=true", async () => {
    await expect(registerRemotePushToken("tok", true)).resolves.toBe("registered");
    expect(registerMock).toHaveBeenCalledTimes(1);
    expect(registerMock).toHaveBeenCalledWith(
      "tok",
      expect.objectContaining({
        expo_push_token: "ExponentPushToken[abc]",
        device_id: "dev-1",
      }),
    );
    expect(registerMock.mock.calls[0]?.[1]).not.toHaveProperty("android_channels");
    expect(updateMeMock).not.toHaveBeenCalled();
  });

  it("registerRemotePushToken tells the API this Android install created the tone channels", async () => {
    Platform.OS = "android";
    await expect(registerRemotePushToken("tok", true)).resolves.toBe("registered");
    expect(registerMock).toHaveBeenCalledWith(
      "tok",
      expect.objectContaining({ android_channels: "tone", platform: "android" }),
    );
  });

  it("records the result only when the OS permission prompt is shown", async () => {
    (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: "denied" });
    (Notifications.requestPermissionsAsync as jest.Mock).mockResolvedValue({ status: "denied" });

    await expect(ensureNotificationPermission("tok")).resolves.toBe(false);
    await new Promise<void>((resolve) => setTimeout(resolve, 0));

    expect(api.recordProductEvents).toHaveBeenCalledWith(
      "tok",
      expect.arrayContaining([
        expect.objectContaining({
          name: "push_permission",
          properties: { status: "denied" },
        }),
      ]),
    );
  });

  it("registerRemotePushToken is a no-op when pushNotificationsEnabled=false", async () => {
    // Without this gate, the backend holds a live push token for a user who
    // opted out and keeps sending them notifications.
    await expect(registerRemotePushToken("tok", false)).resolves.toBe("skipped");
    expect(registerMock).not.toHaveBeenCalled();
    expect(updateMeMock).not.toHaveBeenCalled();
  });

  it("registerRemotePushToken flips the server pref off when OS permission is denied", async () => {
    (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: "denied" });
    (Notifications.requestPermissionsAsync as jest.Mock).mockResolvedValue({ status: "denied" });

    await expect(registerRemotePushToken("tok", true)).resolves.toBe("disabled_permission");
    expect(registerMock).not.toHaveBeenCalled();
    expect(updateMeMock).toHaveBeenCalledWith("tok", { push_notifications_enabled: false });
  });

  it("getNotificationPermissionGranted is read-only and does not prompt", async () => {
    (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: "denied" });
    await expect(getNotificationPermissionGranted()).resolves.toBe(false);
    expect(Notifications.requestPermissionsAsync).not.toHaveBeenCalled();
  });

  it("unregisterRemotePushToken calls the server unregister endpoint", async () => {
    await unregisterRemotePushToken("tok");
    expect(unregisterMock).toHaveBeenCalledTimes(1);
    expect(unregisterMock).toHaveBeenCalledWith(
      "tok",
      expect.objectContaining({ expo_push_token: "ExponentPushToken[abc]" }),
    );
  });

  it("registerRemotePushToken throws when the Expo token cannot be resolved", async () => {
    (Notifications.getExpoPushTokenAsync as jest.Mock).mockRejectedValueOnce(new Error("no eas"));
    await expect(registerRemotePushToken("tok", true)).rejects.toThrow("push_token_unavailable");
    expect(registerMock).not.toHaveBeenCalled();
  });

  it("registerRemotePushToken throws when the API register call fails", async () => {
    registerMock.mockRejectedValueOnce(new Error("rebind rejected"));
    await expect(registerRemotePushToken("tok", true)).rejects.toThrow("rebind rejected");
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

  it("attachPushForegroundSync notifies when permission denial disables the pref", async () => {
    (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: "denied" });
    (Notifications.requestPermissionsAsync as jest.Mock).mockResolvedValue({ status: "denied" });
    const onPref = jest.fn();
    const cleanup = attachPushForegroundSync("tok", true, onPref);
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
    expect(onPref).toHaveBeenCalledWith(false);
    cleanup();
  });

  it("attachPushForegroundSync is a no-op when apiToken is null", () => {
    const cleanup = attachPushForegroundSync(null, true);
    expect(typeof cleanup).toBe("function");
    cleanup();
    expect(registerMock).not.toHaveBeenCalled();
    expect(unregisterMock).not.toHaveBeenCalled();
  });
});

describe("push re-sync on launch, token refresh and foreground", () => {
  const tokenMock = Notifications.getExpoPushTokenAsync as jest.Mock;
  const settle = () => new Promise<void>((resolve) => setTimeout(resolve, 0));
  const foreground = async () => {
    for (const handler of [...mockAppStateHandlers]) handler("active");
    await settle();
  };
  // The caller's session generation: a fresh sign-in per test.
  let session = 100;

  beforeEach(() => {
    session += 1;
    Platform.OS = "ios";
    jest.clearAllMocks();
    mockAppStateHandlers.clear();
    (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: "granted" });
  });
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("re-registers at most twice a day, not on every return to the app", async () => {
    const cleanup = attachPushForegroundSync("tok", true, undefined, session);
    await settle();
    expect(registerMock).toHaveBeenCalledTimes(1);
    expect(tokenMock).toHaveBeenCalledTimes(1);

    // Each sync was a request to Expo's push service plus one to our API.
    await foreground();
    await foreground();
    await foreground();
    expect(registerMock).toHaveBeenCalledTimes(1);
    expect(tokenMock).toHaveBeenCalledTimes(1);

    const now = Date.now();
    jest.spyOn(Date, "now").mockReturnValue(now + 13 * 60 * 60_000);
    await foreground();
    expect(registerMock).toHaveBeenCalledTimes(2);
    cleanup();
  });

  it("does not register again when the hourly token refresh re-attaches", async () => {
    attachPushForegroundSync("tok", true, undefined, session)();
    await settle();
    attachPushForegroundSync("tok-refreshed", true, undefined, session)();
    await settle();
    expect(registerMock).toHaveBeenCalledTimes(1);
  });

  it("registers again after another sign-in on this device", async () => {
    attachPushForegroundSync("tok-a", true, undefined, session)();
    await settle();
    // Another account's sign-in rebinds the device token to that account.
    attachPushForegroundSync("tok-b", true, undefined, session + 1)();
    await settle();
    expect(registerMock).toHaveBeenCalledTimes(2);
    session += 1;
  });

  it("still notices a permission turned off in Settings on return", async () => {
    const onPref = jest.fn();
    const cleanup = attachPushForegroundSync("tok", true, onPref, session);
    await settle();
    (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: "denied" });
    (Notifications.requestPermissionsAsync as jest.Mock).mockResolvedValue({ status: "denied" });
    await foreground();
    expect(onPref).toHaveBeenCalledWith(false);
    expect(updateMeMock).toHaveBeenCalledWith("tok", { push_notifications_enabled: false });
    cleanup();
  });

  it("retries on the next return after a failed sync", async () => {
    registerMock.mockRejectedValueOnce(new Error("offline"));
    const cleanup = attachPushForegroundSync("tok", true, undefined, session);
    await settle();
    await foreground();
    expect(registerMock).toHaveBeenCalledTimes(2);
    cleanup();
  });

  it("unregisters once for a user who turned push off, and retries a failure", async () => {
    unregisterMock.mockRejectedValueOnce(new Error("offline"));
    const cleanup = attachPushForegroundSync("tok", false, undefined, session);
    await settle();
    await foreground();
    await foreground();
    expect(unregisterMock).toHaveBeenCalledTimes(2);
    cleanup();
  });
});

// BUG FIX regression: PushNotificationBootstrap crashed the whole app on web
// (an uncaught overlay covering the entire screen) because
// getLastNotificationResponseAsync/addNotificationResponseReceivedListener
// throw "not available on web" instead of resolving/no-op'ing there — found
// while manually running the app in a browser to test math rendering.
import { Platform } from "react-native";
import { act, render } from "@testing-library/react-native";

import { PushNotificationBootstrap } from "@/components/PushNotificationBootstrap";
import { handlePushNotificationResponse } from "@/lib/pushNotifications";

const mockGetLastNotificationResponseAsync = jest.fn().mockResolvedValue(null);
const mockAddNotificationResponseReceivedListener = jest
  .fn()
  .mockReturnValue({ remove: jest.fn() });
const mockAddNotificationReceivedListener = jest.fn().mockReturnValue({ remove: jest.fn() });

jest.mock("expo-notifications", () => ({
  getLastNotificationResponseAsync: (...args: unknown[]) =>
    mockGetLastNotificationResponseAsync(...args),
  addNotificationResponseReceivedListener: (...args: unknown[]) =>
    mockAddNotificationResponseReceivedListener(...args),
  addNotificationReceivedListener: (...args: unknown[]) =>
    mockAddNotificationReceivedListener(...args),
  cancelScheduledNotificationAsync: jest.fn(async () => undefined),
}));
jest.mock("expo-router", () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
}));
jest.mock("@/contexts/AuthContext", () => ({
  useAuthOptional: () => ({ token: null }),
}));
jest.mock("@/lib/pushNotifications", () => ({
  configurePushNotificationHandler: jest.fn(),
  handlePushNotificationResponse: jest.fn().mockResolvedValue(undefined),
}));
jest.mock("@/lib/todos/todoReminders", () => ({
  cancelTodoReminder: jest.fn(async () => undefined),
}));

describe("PushNotificationBootstrap", () => {
  afterEach(() => {
    Platform.OS = "ios";
    mockGetLastNotificationResponseAsync.mockClear();
    mockAddNotificationResponseReceivedListener.mockClear();
    mockAddNotificationReceivedListener.mockClear();
    jest.mocked(handlePushNotificationResponse).mockClear();
    jest.restoreAllMocks();
  });

  it("handles a failed native startup read without an unhandled rejection", async () => {
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    mockGetLastNotificationResponseAsync.mockRejectedValueOnce(new Error("Keychain unavailable"));
    await render(<PushNotificationBootstrap />);
    await act(async () => {});
    expect(warn).toHaveBeenCalledWith("[notifications] Could not restore startup notification");
    expect(handlePushNotificationResponse).not.toHaveBeenCalled();
  });

  it("ignores a startup response that arrives after the session listener is removed", async () => {
    let finish!: (response: unknown) => void;
    mockGetLastNotificationResponseAsync.mockImplementationOnce(() => new Promise((resolve) => {
      finish = resolve;
    }));
    const screen = await render(<PushNotificationBootstrap />);
    await screen.unmount();
    await act(async () => {
      finish({ notification: { request: { content: { data: { type: "todo_due" } } } } });
    });
    expect(handlePushNotificationResponse).not.toHaveBeenCalled();
  });

  it("BUG FIX regression: does not call the native-only response APIs on web", async () => {
    Platform.OS = "web";
    await render(<PushNotificationBootstrap />);
    expect(mockGetLastNotificationResponseAsync).not.toHaveBeenCalled();
    expect(mockAddNotificationResponseReceivedListener).not.toHaveBeenCalled();
    expect(mockAddNotificationReceivedListener).not.toHaveBeenCalled();
  });

  it("still wires up the response APIs on native platforms", async () => {
    Platform.OS = "ios";
    await render(<PushNotificationBootstrap />);
    expect(mockGetLastNotificationResponseAsync).toHaveBeenCalled();
    expect(mockAddNotificationResponseReceivedListener).toHaveBeenCalled();
    expect(mockAddNotificationReceivedListener).toHaveBeenCalled();
  });
});

// BUG FIX regression: PushNotificationBootstrap crashed the whole app on web
// (an uncaught overlay covering the entire screen) because
// getLastNotificationResponseAsync/addNotificationResponseReceivedListener
// throw "not available on web" instead of resolving/no-op'ing there — found
// while manually running the app in a browser to test math rendering.
import { Platform } from "react-native";
import { render } from "@testing-library/react-native";

import { PushNotificationBootstrap } from "@/components/PushNotificationBootstrap";

const mockGetLastNotificationResponseAsync = jest.fn().mockResolvedValue(null);
const mockAddNotificationResponseReceivedListener = jest
  .fn()
  .mockReturnValue({ remove: jest.fn() });

jest.mock("expo-notifications", () => ({
  getLastNotificationResponseAsync: (...args: unknown[]) =>
    mockGetLastNotificationResponseAsync(...args),
  addNotificationResponseReceivedListener: (...args: unknown[]) =>
    mockAddNotificationResponseReceivedListener(...args),
}));
jest.mock("expo-router", () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
}));
jest.mock("@/contexts/AuthContext", () => ({
  useAuthOptional: () => ({ token: null }),
}));
jest.mock("@/lib/pushNotifications", () => ({
  configurePushNotificationHandler: jest.fn(),
  handlePushNotificationResponse: jest.fn(),
}));

describe("PushNotificationBootstrap", () => {
  afterEach(() => {
    Platform.OS = "ios";
    mockGetLastNotificationResponseAsync.mockClear();
    mockAddNotificationResponseReceivedListener.mockClear();
  });

  it("BUG FIX regression: does not call the native-only response APIs on web", async () => {
    Platform.OS = "web";
    await render(<PushNotificationBootstrap />);
    expect(mockGetLastNotificationResponseAsync).not.toHaveBeenCalled();
    expect(mockAddNotificationResponseReceivedListener).not.toHaveBeenCalled();
  });

  it("still wires up the response APIs on native platforms", async () => {
    Platform.OS = "ios";
    await render(<PushNotificationBootstrap />);
    expect(mockGetLastNotificationResponseAsync).toHaveBeenCalled();
    expect(mockAddNotificationResponseReceivedListener).toHaveBeenCalled();
  });
});

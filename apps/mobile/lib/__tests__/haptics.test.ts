const mockVibrate = jest.fn();
const mockImpactAsync = jest.fn().mockResolvedValue(undefined);
const mockSelectionAsync = jest.fn().mockResolvedValue(undefined);
const mockNotificationAsync = jest.fn().mockResolvedValue(undefined);

jest.mock("react-native", () => ({
  Platform: { OS: "ios" },
  Vibration: { vibrate: mockVibrate },
}));

jest.mock("expo-haptics", () => ({
  ImpactFeedbackStyle: { Light: "light", Medium: "medium" },
  NotificationFeedbackType: { Success: "success", Warning: "warning" },
  impactAsync: mockImpactAsync,
  selectionAsync: mockSelectionAsync,
  notificationAsync: mockNotificationAsync,
}));

import { Platform } from "react-native";

import {
  impactMedium,
  notifyDestructive,
  notifySuccess,
  notifyWarning,
  resetHapticsAvailabilityForTests,
  selection,
  tap,
} from "@/lib/haptics";

describe("haptics", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockImpactAsync.mockResolvedValue(undefined);
    mockSelectionAsync.mockResolvedValue(undefined);
    mockNotificationAsync.mockResolvedValue(undefined);
    resetHapticsAvailabilityForTests();
  });

  it("tap uses iOS impact on ios", async () => {
    Platform.OS = "ios";
    tap();
    await Promise.resolve();
    expect(mockImpactAsync).toHaveBeenCalledWith("light");
    expect(mockVibrate).not.toHaveBeenCalled();
  });

  it("tap uses expo haptics on android before vibration", async () => {
    Platform.OS = "android";
    tap();
    await Promise.resolve();
    expect(mockImpactAsync).toHaveBeenCalledWith("light");
    expect(mockVibrate).not.toHaveBeenCalled();
  });

  it("falls back to a short vibration when android haptics are unavailable", async () => {
    Platform.OS = "android";
    mockImpactAsync.mockRejectedValueOnce(new Error("unavailable"));
    tap();
    await Promise.resolve();
    await Promise.resolve();
    expect(mockVibrate).toHaveBeenCalledWith(10);
  });

  it("selection uses selectionAsync on both platforms", async () => {
    Platform.OS = "ios";
    selection();
    Platform.OS = "android";
    selection();
    await Promise.resolve();
    expect(mockSelectionAsync).toHaveBeenCalledTimes(2);
  });

  it("impactMedium uses medium impact on ios", async () => {
    Platform.OS = "ios";
    impactMedium();
    await Promise.resolve();
    expect(mockImpactAsync).toHaveBeenCalledWith("medium");
  });

  it("notifySuccess and notifyWarning map to notification feedback", async () => {
    Platform.OS = "ios";
    notifySuccess();
    notifyWarning();
    await Promise.resolve();
    expect(mockNotificationAsync).toHaveBeenCalledWith("success");
    expect(mockNotificationAsync).toHaveBeenCalledWith("warning");
  });

  it("emits one warning notification for a confirmed destructive action", async () => {
    Platform.OS = "ios";
    notifyDestructive();
    await Promise.resolve();
    expect(mockNotificationAsync).toHaveBeenCalledTimes(1);
    expect(mockNotificationAsync).toHaveBeenCalledWith("warning");
  });
});

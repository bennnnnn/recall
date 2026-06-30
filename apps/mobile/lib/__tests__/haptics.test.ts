const mockVibrate = jest.fn();
const mockImpactAsync = jest.fn().mockResolvedValue(undefined);
const mockSelectionAsync = jest.fn().mockResolvedValue(undefined);
const mockNotificationAsync = jest.fn().mockResolvedValue(undefined);

jest.mock("react-native", () => ({
  Platform: { OS: "ios" },
  Vibration: { vibrate: mockVibrate },
}));

jest.mock("expo-haptics", () => ({
  ImpactFeedbackStyle: { Light: "light" },
  NotificationFeedbackType: { Success: "success", Warning: "warning" },
  impactAsync: mockImpactAsync,
  selectionAsync: mockSelectionAsync,
  notificationAsync: mockNotificationAsync,
}));

import { Platform } from "react-native";

import { notifySuccess, notifyWarning, selection, tap } from "@/lib/haptics";

describe("haptics", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("tap uses iOS impact on ios", () => {
    Platform.OS = "ios";
    tap();
    expect(mockImpactAsync).toHaveBeenCalledWith("light");
  });

  it("tap vibrates on android", () => {
    Platform.OS = "android";
    tap();
    expect(mockVibrate).toHaveBeenCalledWith(10);
  });

  it("selection uses selectionAsync on ios", () => {
    Platform.OS = "ios";
    selection();
    expect(mockSelectionAsync).toHaveBeenCalled();
  });

  it("notifySuccess and notifyWarning map to notification feedback", () => {
    Platform.OS = "ios";
    notifySuccess();
    notifyWarning();
    expect(mockNotificationAsync).toHaveBeenCalledWith("success");
    expect(mockNotificationAsync).toHaveBeenCalledWith("warning");
  });
});

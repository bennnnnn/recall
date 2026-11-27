import {
  allowReminderAlerts,
  resetAlertsOffNoticeForTest,
  shouldTellAlertsOff,
} from "@/features/todos/model/reminderAlerts";
import {
  askNotificationPermission,
  notificationPermissionState,
} from "@/features/notifications/model/pushNotifications";

jest.mock("@/features/notifications/model/pushNotifications", () => ({
  askNotificationPermission: jest.fn(),
  notificationPermissionState: jest.fn(async () => "askable"),
}));

beforeEach(() => {
  jest.clearAllMocks();
  jest.mocked(notificationPermissionState).mockResolvedValue("askable");
  resetAlertsOffNoticeForTest();
});

it.each([
  ["granted", "on"],
  ["denied", "off"],
  ["not_now", "not_now"],
] as const)("an ask that comes to %s means alerts are %s", async (answer, alerts) => {
  jest.mocked(askNotificationPermission).mockResolvedValue(answer);
  await expect(allowReminderAlerts()).resolves.toBe(alerts);
});

it("after Not now, the next save this launch does not explain again", async () => {
  jest.mocked(askNotificationPermission).mockResolvedValue("not_now");
  await allowReminderAlerts();
  await expect(allowReminderAlerts()).resolves.toBe("not_now");
  expect(askNotificationPermission).toHaveBeenCalledTimes(1);
  // Allowed in Settings meanwhile: on, still without asking.
  jest.mocked(notificationPermissionState).mockResolvedValue("granted");
  await expect(allowReminderAlerts()).resolves.toBe("on");
  expect(askNotificationPermission).toHaveBeenCalledTimes(1);
});

it("after Not now, a refusal for good since (the Settings switch's ask) reads as off", async () => {
  jest.mocked(askNotificationPermission).mockResolvedValue("not_now");
  await allowReminderAlerts();
  jest.mocked(notificationPermissionState).mockResolvedValue("denied");
  await expect(allowReminderAlerts()).resolves.toBe("off");
});

it("a failed ask counts as off, never as an error", async () => {
  jest.mocked(askNotificationPermission).mockRejectedValue(new Error("native"));
  await expect(allowReminderAlerts()).resolves.toBe("off");
});

it("tells the user once per launch", () => {
  expect(shouldTellAlertsOff()).toBe(true);
  expect(shouldTellAlertsOff()).toBe(false);
  resetAlertsOffNoticeForTest();
  expect(shouldTellAlertsOff()).toBe(true);
});

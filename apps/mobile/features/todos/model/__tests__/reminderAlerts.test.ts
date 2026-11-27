import {
  allowReminderAlerts,
  resetAlertsOffNoticeForTest,
  shouldTellAlertsOff,
} from "@/features/todos/model/reminderAlerts";
import {
  askNotificationPermission,
  getNotificationPermissionGranted,
} from "@/features/notifications/model/pushNotifications";

jest.mock("@/features/notifications/model/pushNotifications", () => ({
  askNotificationPermission: jest.fn(),
  getNotificationPermissionGranted: jest.fn(async () => false),
}));

beforeEach(() => {
  jest.clearAllMocks();
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
  jest.mocked(getNotificationPermissionGranted).mockResolvedValue(true);
  await expect(allowReminderAlerts()).resolves.toBe("on");
  expect(askNotificationPermission).toHaveBeenCalledTimes(1);
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

import * as Notifications from "expo-notifications";

import { canRemindTrialEnd, remindBeforeTrialEnds } from "@/features/billing/model/trialReminder";
import { ensureNotificationPermission } from "@/features/notifications/model/pushNotifications";
import { reportFailure } from "@/lib/sentry";

jest.mock("react-native", () => ({ Platform: { OS: "ios" } }));
jest.mock("expo-notifications", () => ({
  getPermissionsAsync: jest.fn(),
  cancelScheduledNotificationAsync: jest.fn(async () => undefined),
  scheduleNotificationAsync: jest.fn(async () => "id"),
  SchedulableTriggerInputTypes: { DATE: "date" },
}));
jest.mock("@/features/notifications/model/pushNotifications", () => ({
  ensureNotificationPermission: jest.fn(async () => true),
}));
jest.mock("@/features/notifications/model/notificationChannels", () => ({
  AndroidNotificationChannel: { reminders: "recall-reminders-v2" },
  notificationSound: () => "default",
}));
jest.mock("@/lib/i18n", () => ({ __esModule: true, default: { t: (key: string) => key } }));
jest.mock("@/lib/sentry", () => ({ reportFailure: jest.fn() }));

const NOW = new Date(2026, 10, 23, 10, 0);
const ENDS = new Date(2026, 10, 26, 10, 0);

beforeEach(() => {
  jest.clearAllMocks();
  jest.mocked(ensureNotificationPermission).mockResolvedValue(true);
});

describe("remindBeforeTrialEnds", () => {
  it("sets one reminder for a day before the trial ends", async () => {
    await expect(remindBeforeTrialEnds(ENDS, "$59.99 / year", NOW)).resolves.toBe(true);
    const [request] = jest.mocked(Notifications.scheduleNotificationAsync).mock.calls[0];
    expect(request.identifier).toBe("recall-trial-ends");
    expect(request.trigger).toEqual({ type: "date", date: new Date(2026, 10, 25, 10, 0) });
    // A trial started again replaces the reminder, never adds a second.
    expect(Notifications.cancelScheduledNotificationAsync).toHaveBeenCalledWith("recall-trial-ends");
  });

  it("sets nothing when notifications are refused", async () => {
    jest.mocked(ensureNotificationPermission).mockResolvedValue(false);
    await expect(remindBeforeTrialEnds(ENDS, "$59.99 / year", NOW)).resolves.toBe(false);
    expect(Notifications.scheduleNotificationAsync).not.toHaveBeenCalled();
  });

  it("sets nothing for a trial a day or less from its end", async () => {
    await expect(remindBeforeTrialEnds(new Date(2026, 10, 24, 9, 0), "$7.99 / month", NOW)).resolves.toBe(false);
    expect(ensureNotificationPermission).not.toHaveBeenCalled();
  });

  it("never fails the purchase: a scheduling error is reported and answered false", async () => {
    const failure = new Error("scheduler down");
    jest.mocked(Notifications.scheduleNotificationAsync).mockRejectedValueOnce(failure);
    await expect(remindBeforeTrialEnds(ENDS, "$59.99 / year", NOW)).resolves.toBe(false);
    expect(reportFailure).toHaveBeenCalledWith("trial_reminder", failure);
  });
});

describe("canRemindTrialEnd", () => {
  it.each([
    [{ status: "granted", canAskAgain: false }, true],
    [{ status: "undetermined", canAskAgain: true }, true],
    [{ status: "denied", canAskAgain: false }, false],
  ])("answers %j with %s", async (permission, expected) => {
    jest.mocked(Notifications.getPermissionsAsync).mockResolvedValueOnce(permission as never);
    await expect(canRemindTrialEnd()).resolves.toBe(expected);
  });

  it("promises nothing when the phone cannot say", async () => {
    jest.mocked(Notifications.getPermissionsAsync).mockRejectedValueOnce(new Error("no module"));
    await expect(canRemindTrialEnd()).resolves.toBe(false);
    expect(reportFailure).toHaveBeenCalledWith("trial_reminder", expect.any(Error));
  });
});

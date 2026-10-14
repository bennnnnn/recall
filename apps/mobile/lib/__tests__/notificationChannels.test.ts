import * as Notifications from "expo-notifications";

import { ensureAndroidNotificationChannels } from "@/lib/notificationChannels";

jest.mock("expo-notifications", () => ({
  setNotificationChannelAsync: jest.fn(),
  AndroidImportance: { HIGH: 4, DEFAULT: 3 },
}));

describe("notification channels", () => {
  it("creates only the reminders channel", async () => {
    await ensureAndroidNotificationChannels({ reminders: "Reminders" });
    expect(Notifications.setNotificationChannelAsync).toHaveBeenCalledTimes(1);
    expect(Notifications.setNotificationChannelAsync).toHaveBeenCalledWith(
      "recall-reminders-v2",
      expect.objectContaining({ name: "Reminders", importance: 4 }),
    );
  });
});

jest.mock("expo-notifications", () => ({
  setNotificationChannelAsync: jest.fn(),
  AndroidImportance: { HIGH: 4, DEFAULT: 3 },
}));

import { androidChannelForPushType } from "@/lib/notificationChannels";

describe("notification channels", () => {
  it("separates reminders, learning, and inbox", () => {
    expect(androidChannelForPushType("todo_reminder")).toBe("recall-reminders-v2");
    expect(androidChannelForPushType("calendar_nudge")).toBe("recall-reminders-v2");
    expect(androidChannelForPushType("learning_review")).toBe("recall-learning-v2");
    expect(androidChannelForPushType("email_suggestion")).toBe("recall-inbox-v2");
    expect(androidChannelForPushType(undefined)).toBe("recall-reminders-v2");
  });
});

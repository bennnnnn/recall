jest.mock("expo-notifications", () => ({
  setNotificationChannelAsync: jest.fn(),
  AndroidImportance: { HIGH: 4, DEFAULT: 3 },
}));

import { androidChannelForPushType } from "@/lib/notificationChannels";

describe("notification channels", () => {
  it("separates reminders, learning, and inbox", () => {
    expect(androidChannelForPushType("todo_reminder")).toBe("recall-reminders");
    expect(androidChannelForPushType("calendar_nudge")).toBe("recall-reminders");
    expect(androidChannelForPushType("learning_review")).toBe("recall-learning");
    expect(androidChannelForPushType("email_suggestion")).toBe("recall-inbox");
    expect(androidChannelForPushType(undefined)).toBe("recall-reminders");
  });
});

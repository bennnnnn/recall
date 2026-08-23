import {
  isRemotePushTrigger,
  todoIdFromNotificationData,
} from "@/lib/todos/todoReminderPush";

describe("todo reminder push helpers", () => {
  it("reads todo_id from remote todo reminder payloads", () => {
    expect(
      todoIdFromNotificationData({ type: "todo_reminder", todo_id: "abc" }),
    ).toBe("abc");
    expect(todoIdFromNotificationData({ type: "todo_due", todo_id: "abc" })).toBe("abc");
    expect(todoIdFromNotificationData({ type: "learning_nudge", todo_id: "abc" })).toBe(
      null,
    );
    expect(todoIdFromNotificationData({ type: "todo_reminder" })).toBe(null);
  });

  it("treats only push triggers as remote", () => {
    expect(isRemotePushTrigger({ type: "push" })).toBe(true);
    expect(isRemotePushTrigger({ type: "date", date: new Date() })).toBe(false);
    expect(isRemotePushTrigger(null)).toBe(false);
  });
});

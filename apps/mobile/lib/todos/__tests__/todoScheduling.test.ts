import * as Notifications from "expo-notifications";
import { syncTodoReminders, cancelAllTodoReminders, todoNotificationId } from "@/lib/todos/todoReminders";
import { ensureNotificationPermission } from "@/lib/pushNotifications";
import type { Todo } from "@/lib/api/types";
let mockSession = 1;
const scheduled = new Map<string, unknown>();
const todo: Todo = { id: "t1", content: "Flight", topic: "Reminders", checked: false,
  due_at: "2099-01-01T12:00:00Z", created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z", sort_order: null, chat_id: null };
jest.mock("react-native", () => ({ Platform: { OS: "ios" } }));
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));
jest.mock("@/lib/pushNotifications", () => ({ ensureNotificationPermission: jest.fn(async () => true) }));
jest.mock("@/lib/reminderPrefs", () => ({ getReminderLeadMs: jest.fn(async () => 600_000) }));
jest.mock("@/lib/i18n", () => ({ t: (key: string) => key }));
jest.mock("expo-notifications", () => ({
  getPermissionsAsync: jest.fn(), getAllScheduledNotificationsAsync: jest.fn(),
  cancelScheduledNotificationAsync: jest.fn(), scheduleNotificationAsync: jest.fn(),
  SchedulableTriggerInputTypes: { DATE: "date" },
}));
beforeEach(async () => {
  jest.clearAllMocks(); mockSession = 1; scheduled.clear();
  jest.mocked(Notifications.getPermissionsAsync).mockResolvedValue({ status: "granted" } as never);
  jest.mocked(Notifications.getAllScheduledNotificationsAsync).mockImplementation(async () =>
    [...scheduled.keys()].map((identifier) => ({ identifier })) as never);
  jest.mocked(Notifications.cancelScheduledNotificationAsync).mockImplementation(async (id) => { scheduled.delete(id); });
  jest.mocked(Notifications.scheduleNotificationAsync).mockImplementation(async (item) => {
    scheduled.set(item.identifier!, item.trigger); return item.identifier!;
  });
  await cancelAllTodoReminders();
});

it("never requests OS permission from background synchronization", async () => {
  await syncTodoReminders([todo], { pushEnabled: false });
  expect(ensureNotificationPermission).not.toHaveBeenCalled();
  expect(Notifications.getPermissionsAsync).toHaveBeenCalled();
});

it("waits for an already-started native schedule before cancelling on signout", async () => {
  let finish!: () => void;
  let started!: () => void;
  const began = new Promise<void>((resolve) => { started = resolve; });
  jest.mocked(Notifications.scheduleNotificationAsync).mockImplementationOnce(async (item) => {
    started(); await new Promise<void>((resolve) => { finish = resolve; });
    scheduled.set(item.identifier!, item.trigger); return item.identifier!;
  });
  const old = syncTodoReminders([todo], { pushEnabled: false });
  await began;
  mockSession++;
  const clearing = cancelAllTodoReminders();
  finish();
  await Promise.all([old, clearing]);
  expect(scheduled.size).toBe(0);
});

it("keeps the latest due date when native scheduling finishes out of order", async () => {
  let finish!: () => void;
  let started!: () => void;
  const began = new Promise<void>((resolve) => { started = resolve; });
  jest.mocked(Notifications.scheduleNotificationAsync).mockImplementationOnce(async (item) => {
    started(); await new Promise<void>((resolve) => { finish = resolve; });
    scheduled.set(item.identifier!, item.trigger); return item.identifier!;
  });
  const old = syncTodoReminders([todo], { pushEnabled: false });
  await began;
  const changed = { ...todo, due_at: "2099-01-02T12:00:00Z" };
  const latest = syncTodoReminders([changed], { pushEnabled: false });
  await Promise.resolve(); await Promise.resolve();
  finish();
  await Promise.all([old, latest]);
  expect(scheduled.get(todoNotificationId(todo.id))).toMatchObject({ date: new Date("2099-01-02T11:50:00Z") });
});

it("removes local reminders when remote push owns delivery", async () => {
  scheduled.set(todoNotificationId(todo.id), {});
  await syncTodoReminders([todo], { pushEnabled: true });
  expect(scheduled.size).toBe(0);
});

it("does not schedule unconfirmed optimistic reminders", async () => {
  await syncTodoReminders([{ ...todo, id: "local-create" }], { pushEnabled: false });
  expect(Notifications.scheduleNotificationAsync).not.toHaveBeenCalled();
});

it("ignores a sync retained from an old account before touching the device", async () => {
  mockSession++;
  jest.mocked(Notifications.getAllScheduledNotificationsAsync).mockClear();
  await syncTodoReminders([todo], { pushEnabled: false, session: mockSession - 1 });
  expect(Notifications.getAllScheduledNotificationsAsync).not.toHaveBeenCalled();
  expect(Notifications.scheduleNotificationAsync).not.toHaveBeenCalled();
});

it("does not prompt or schedule when notification permission is denied", async () => {
  jest.mocked(Notifications.getPermissionsAsync).mockResolvedValue({ status: "denied" } as never);
  await syncTodoReminders([todo], { pushEnabled: false });
  expect(ensureNotificationPermission).not.toHaveBeenCalled();
  expect(Notifications.scheduleNotificationAsync).not.toHaveBeenCalled();
});

it("does not repeat an unchanged reminder after another list refresh", async () => {
  await syncTodoReminders([todo], { pushEnabled: false });
  scheduled.clear(); // The existing alert was already delivered.
  await syncTodoReminders([todo], { pushEnabled: false });
  expect(Notifications.scheduleNotificationAsync).toHaveBeenCalledTimes(1);
});

it("allows a later job to retry after native scheduling fails", async () => {
  jest.mocked(Notifications.scheduleNotificationAsync).mockRejectedValueOnce(new Error("native unavailable"));
  await expect(syncTodoReminders([todo], { pushEnabled: false })).rejects.toThrow("native unavailable");
  await syncTodoReminders([todo], { pushEnabled: false });
  expect(scheduled.has(todoNotificationId(todo.id))).toBe(true);
});

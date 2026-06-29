import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

import type { Todo } from "@/lib/api";
import { ensureNotificationPermission } from "@/lib/pushNotifications";

export { ensureNotificationPermission };

const TODO_PREFIX = "todo-due-";
const ANDROID_CHANNEL = "todo-reminders";
/** Fire local reminders this many ms before `due_at`. */
export const REMINDER_LEAD_MS = 10 * 60 * 1000;

let androidChannelReady = false;

export function todoNotificationId(todoId: string): string {
  return `${TODO_PREFIX}${todoId}`;
}

/** When to schedule the local notification (null if due is past or invalid). */
export function reminderNotifyDate(dueAt: Date, now = new Date()): Date | null {
  const dueMs = dueAt.getTime();
  if (Number.isNaN(dueMs) || dueMs <= now.getTime()) return null;

  const leadMs = dueMs - REMINDER_LEAD_MS;
  if (leadMs <= now.getTime()) {
    return new Date(now.getTime() + 2_000);
  }
  return new Date(leadMs);
}

function formatDueTime(due: Date): string {
  return due.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

async function ensureAndroidChannel(): Promise<void> {
  if (Platform.OS !== "android" || androidChannelReady) return;
  await Notifications.setNotificationChannelAsync(ANDROID_CHANNEL, {
    name: "Todo reminders",
    importance: Notifications.AndroidImportance.HIGH,
    vibrationPattern: [0, 250, 250, 250],
  });
  androidChannelReady = true;
}

export async function cancelTodoReminder(todoId: string): Promise<void> {
  if (Platform.OS === "web") return;
  await Notifications.cancelScheduledNotificationAsync(todoNotificationId(todoId)).catch(
    () => {},
  );
}

export async function scheduleTodoReminder(todo: Todo): Promise<void> {
  if (Platform.OS === "web") return;
  await cancelTodoReminder(todo.id);
  if (todo.checked || !todo.due_at) return;

  const due = new Date(todo.due_at);
  const notifyAt = reminderNotifyDate(due);
  if (!notifyAt) return;

  const granted = await ensureNotificationPermission();
  if (!granted) return;

  await Notifications.scheduleNotificationAsync({
    identifier: todoNotificationId(todo.id),
    content: {
      title: "Reminder",
      body: `${todo.content} · due ${formatDueTime(due)}`,
      data: {
        type: "todo_due",
        screen: "todos",
        focus: "reminders",
        todo_id: todo.id,
        topic: todo.topic,
      },
      ...(Platform.OS === "android" ? { channelId: ANDROID_CHANNEL } : {}),
    },
    trigger: {
      type: Notifications.SchedulableTriggerInputTypes.DATE,
      date: notifyAt,
    },
  });
}

export async function syncTodoReminders(todos: Todo[]): Promise<void> {
  if (Platform.OS === "web") return;
  await ensureAndroidChannel();

  const openWithDue = todos.filter((todo) => !todo.checked && todo.due_at);
  const keepIds = new Set(openWithDue.map((todo) => todoNotificationId(todo.id)));

  const scheduled = await Notifications.getAllScheduledNotificationsAsync();
  await Promise.all(
    scheduled
      .filter((n) => n.identifier.startsWith(TODO_PREFIX) && !keepIds.has(n.identifier))
      .map((n) => Notifications.cancelScheduledNotificationAsync(n.identifier).catch(() => {})),
  );

  for (const todo of openWithDue) {
    await scheduleTodoReminder(todo);
  }
}

export async function cancelAllTodoReminders(): Promise<void> {
  if (Platform.OS === "web") return;
  const scheduled = await Notifications.getAllScheduledNotificationsAsync();
  await Promise.all(
    scheduled
      .filter((n) => n.identifier.startsWith(TODO_PREFIX))
      .map((n) => Notifications.cancelScheduledNotificationAsync(n.identifier).catch(() => {})),
  );
}

import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

import type { Todo } from "@/lib/api";
import { ensureNotificationPermission } from "@/lib/pushNotifications";
import i18n from "@/lib/i18n";
import { getReminderLeadMs } from "@/lib/reminderPrefs";
import {
  DEFAULT_REMINDER_LEAD_MINUTES,
  leadMsFromMinutes,
  reminderNotifyDate,
} from "@/lib/reminderTiming";

export { ensureNotificationPermission };

const TODO_PREFIX = "todo-due-";
const ANDROID_CHANNEL = "todo-reminders";

/** Default lead before `due_at` when prefs have not loaded yet. */
export const REMINDER_LEAD_MS = leadMsFromMinutes(DEFAULT_REMINDER_LEAD_MINUTES);

let androidChannelReady = false;

export function todoNotificationId(todoId: string): string {
  return `${TODO_PREFIX}${todoId}`;
}

export { reminderNotifyDate };

function formatDueTime(due: Date): string {
  return due.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

async function ensureAndroidChannel(): Promise<void> {
  if (Platform.OS !== "android" || androidChannelReady) return;
  await Notifications.setNotificationChannelAsync(ANDROID_CHANNEL, {
    name: i18n.t("notifications.todo_channel"),
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
  const leadMs = await getReminderLeadMs();
  const notifyAt = reminderNotifyDate(due, new Date(), leadMs);
  if (!notifyAt) return;

  const granted = await ensureNotificationPermission();
  if (!granted) return;

  await Notifications.scheduleNotificationAsync({
    identifier: todoNotificationId(todo.id),
    content: {
      title: i18n.t("notifications.todo_reminder_title"),
      body: i18n.t("notifications.todo_reminder_body", {
        content: todo.content,
        time: formatDueTime(due),
      }),
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

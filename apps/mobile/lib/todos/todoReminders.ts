import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

import type { Todo } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import i18n from "@/lib/i18n";
import { getReminderLeadMs } from "@/lib/reminderPrefs";
import { DEFAULT_REMINDER_LEAD_MINUTES, leadMsFromMinutes, reminderNotifyDate } from "@/lib/todos/reminderTiming";
import { shouldSyncLocalTodoReminders } from "@/lib/todos/todoReminderPush";

export { ensureNotificationPermission } from "@/lib/pushNotifications";
const TODO_PREFIX = "todo-due-";
const ANDROID_CHANNEL = "todo-reminders";
export const REMINDER_LEAD_MS = leadMsFromMinutes(DEFAULT_REMINDER_LEAD_MINUTES);
type ReminderOptions = { pushEnabled?: boolean | null; session?: number; leadMinutes?: number };
type IsCurrent = () => boolean;
let androidChannelReady = false;
let revision = 0;
let pending: Promise<void> = Promise.resolve();
const scheduledVersions = new Map<string, string>();

/** Native writes finish in order; newer full-list intent invalidates older work. */
function enqueue(session: number, operation: (current: IsCurrent) => Promise<void>, supersede = true): Promise<void> {
  if (Platform.OS === "web" || session !== getSessionGeneration()) return Promise.resolve();
  const request = supersede ? ++revision : revision;
  const current = () => session === getSessionGeneration() && request === revision;
  const task = pending.then(async () => { if (current()) await operation(current); });
  pending = task.then(() => {}, () => {});
  return task;
}

export function todoNotificationId(todoId: string): string { return `${TODO_PREFIX}${todoId}`; }
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

async function cancelMatching(matches: (id: string) => boolean, current: IsCurrent): Promise<void> {
  const scheduled = await Notifications.getAllScheduledNotificationsAsync();
  if (!current()) return;
  for (const id of scheduledVersions.keys()) if (matches(id)) scheduledVersions.delete(id);
  // Wait for every started native cancellation before another job may schedule.
  const results = await Promise.allSettled(scheduled.filter((item) => matches(item.identifier))
    .map((item) => Notifications.cancelScheduledNotificationAsync(item.identifier)));
  const failure = results.find((result) => result.status === "rejected");
  if (failure?.status === "rejected") throw failure.reason;
}
function matchesTodo(todoId: string): (id: string) => boolean {
  const id = todoNotificationId(todoId);
  return (candidate) => candidate === id || candidate.startsWith(`${id}-`);
}
export function cancelTodoReminder(todoId: string): Promise<void> {
  return enqueue(getSessionGeneration(), (current) => cancelMatching(matchesTodo(todoId), current), false);
}

async function schedule(todo: Todo, leadMs: number, current: IsCurrent): Promise<void> {
  if (!current() || todo.id.startsWith("local-") || todo.checked || !todo.due_at) return;
  const due = new Date(todo.due_at);
  const notifyAt = reminderNotifyDate(due, new Date(), leadMs);
  if (!notifyAt) return;
  const id = todoNotificationId(todo.id);
  const version = JSON.stringify([todo.content, todo.due_at, todo.topic, leadMs]);
  // Repeated list refreshes must not schedule another alert in the lead window.
  if (scheduledVersions.get(id) === version) return;
  await cancelMatching(matchesTodo(todo.id), current);
  if (!current()) return;
  await Notifications.scheduleNotificationAsync({
    identifier: id,
    content: {
      title: i18n.t("notifications.todo_reminder_title"),
      body: i18n.t("notifications.todo_reminder_body", { content: todo.content, time: formatDueTime(due) }),
      data: { type: "todo_due", screen: "todos", focus: "reminders", todo_id: todo.id, topic: todo.topic },
      ...(Platform.OS === "android" ? { channelId: ANDROID_CHANNEL } : {}),
    },
    trigger: { type: Notifications.SchedulableTriggerInputTypes.DATE, date: notifyAt },
  });
  if (current()) scheduledVersions.set(id, version);
}

async function permitted(current: IsCurrent): Promise<boolean> {
  await ensureAndroidChannel();
  if (!current()) return false;
  // Permission prompts belong to explicit user actions, never a background refresh.
  const permission = await Notifications.getPermissionsAsync();
  return current() && permission.status === "granted";
}
export function scheduleTodoReminder(todo: Todo, options?: ReminderOptions): Promise<void> {
  return enqueue(options?.session ?? getSessionGeneration(), async (current) => {
    if (!await permitted(current)) return;
    const leadMs = options?.leadMinutes == null ? await getReminderLeadMs() : leadMsFromMinutes(options.leadMinutes);
    await schedule(todo, leadMs, current);
  }, false);
}

export function syncTodoReminders(todos: Todo[], options?: ReminderOptions): Promise<void> {
  return enqueue(options?.session ?? getSessionGeneration(), async (current) => {
    if (!shouldSyncLocalTodoReminders(options?.pushEnabled)) {
      await cancelMatching((id) => id.startsWith(TODO_PREFIX), current);
      return;
    }
    const open = todos.filter((todo) => !todo.checked && !todo.id.startsWith("local-") &&
      todo.due_at && new Date(todo.due_at).getTime() > Date.now());
    const keepIds = new Set(open.map((todo) => todoNotificationId(todo.id)));
    await cancelMatching((id) => id.startsWith(TODO_PREFIX) && !keepIds.has(id), current);
    if (!open.length || !current() || !await permitted(current)) return;
    const leadMs = options?.leadMinutes == null ? await getReminderLeadMs() : leadMsFromMinutes(options.leadMinutes);
    for (const todo of open) {
      if (!current()) return;
      await schedule(todo, leadMs, current);
    }
  });
}

/** Invalidates queued schedules immediately, then cancels after any native write settles. */
export function cancelAllTodoReminders(): Promise<void> {
  return enqueue(getSessionGeneration(), (current) => cancelMatching((id) => id.startsWith(TODO_PREFIX), current));
}

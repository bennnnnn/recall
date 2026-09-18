import type { TFunction } from "i18next";

import { automationFrequencyMessageKey } from "@/lib/automations/frequency";
import type { Automation, AutomationFrequency } from "@/lib/api/types";
import { presentShareSheet } from "@/lib/share";

/** Neutral (non-"overdue") date/time label for an automation's next run —
 * `describeDueAt` in lib/todos/dueDate.ts is reminder-specific ("Overdue by
 * N days") and would misread a just-passed scheduler tick as a missed task. */
export function formatScheduleAt(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";

  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const dayDiff = Math.round((startOfDate.getTime() - startOfToday.getTime()) / 86_400_000);
  const time = date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });

  if (dayDiff === 0) return time;
  if (dayDiff === 1 || dayDiff === -1) {
    const dayLabel = dayDiff === 1 ? "Tomorrow" : "Yesterday";
    return `${dayLabel}, ${time}`;
  }
  if (Math.abs(dayDiff) <= 6) {
    return `${date.toLocaleDateString(undefined, { weekday: "short" })}, ${time}`;
  }
  return `${date.toLocaleDateString(undefined, { month: "short", day: "numeric" })}, ${time}`;
}

export function describeLastRun(automation: Automation, t: TFunction): string {
  if (!automation.last_run_at || !automation.last_run_status) {
    return t("automations.last_run_never");
  }
  const date = formatScheduleAt(automation.last_run_at);
  if (automation.last_run_status === "ok") return t("automations.last_run_ok", { date });
  if (automation.last_run_status === "skipped_quota") {
    return t("automations.last_run_skipped_quota", { date });
  }
  return t("automations.last_run_error", { date });
}

const WEEKDAY_NAMES = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
] as const;

const WEEKDAY_PLURAL: Record<string, string> = {
  Sunday: "Sundays",
  Monday: "Mondays",
  Tuesday: "Tuesdays",
  Wednesday: "Wednesdays",
  Thursday: "Thursdays",
  Friday: "Fridays",
  Saturday: "Saturdays",
};

/** Describe the "Schedule" row label based on frequency + next_run_at. */
export function describeSchedule(
  frequency: AutomationFrequency,
  nextRunAt: string,
): string {
  const date = new Date(nextRunAt);
  if (Number.isNaN(date.getTime())) return "";

  switch (frequency) {
    case "daily":
      return "Every day";
    case "weekdays":
      return "Mon – Fri";
    case "weekly": {
      const day = WEEKDAY_NAMES[date.getDay()];
      return WEEKDAY_PLURAL[day] ?? day;
    }
    case "monthly": {
      const dayOfMonth = date.getDate();
      const suffix =
        dayOfMonth === 1 || dayOfMonth === 21 || dayOfMonth === 31
          ? "st"
          : dayOfMonth === 2 || dayOfMonth === 22
            ? "nd"
            : dayOfMonth === 3 || dayOfMonth === 23
              ? "rd"
              : "th";
      return `${dayOfMonth}${suffix} of every month`;
    }
    case "once":
      return date.toLocaleDateString(undefined, {
        weekday: "short",
        month: "short",
        day: "numeric",
      });
    default:
      return "";
  }
}

/** Get the weekday index (0=Sun..6=Sat) from an ISO datetime. */
export function weekdayOfNextRun(nextRunAt: string): number {
  return new Date(nextRunAt).getDay();
}

/** Get the day-of-month (1-31) from an ISO datetime. */
export function dayOfMonthOfNextRun(nextRunAt: string): number {
  return new Date(nextRunAt).getDate();
}

/** Adjust `nextRunAt` so the weekday becomes `targetDay` (0=Sun..6=Sat),
 * moving forward to the next occurrence while preserving the time. */
export function adjustWeekday(nextRunAt: string, targetDay: number): Date {
  const d = new Date(nextRunAt);
  const current = d.getDay();
  let diff = targetDay - current;
  if (diff <= 0) diff += 7;
  d.setDate(d.getDate() + diff);
  return d;
}

/** Adjust `nextRunAt` so the day-of-month becomes `targetDay` (1-28),
 * moving forward to the next month if needed, preserving the time. */
export function adjustDayOfMonth(nextRunAt: string, targetDay: number): Date {
  const d = new Date(nextRunAt);
  const current = d.getDate();
  if (targetDay > current) {
    d.setDate(targetDay);
  } else {
    d.setMonth(d.getMonth() + 1);
    d.setDate(targetDay);
  }
  return d;
}

// Time presets

export type TimePreset = "morning" | "afternoon" | "evening" | "custom";

export const TIME_PRESETS: { key: TimePreset; hour: number; minute: number }[] = [
  { key: "morning", hour: 9, minute: 0 },
  { key: "afternoon", hour: 13, minute: 0 },
  { key: "evening", hour: 18, minute: 0 },
];

/** Map an hour to a time preset label, or null if it doesn't match a preset. */
export function timePresetFromHour(hour: number): TimePreset {
  if (hour >= 5 && hour < 12) return "morning";
  if (hour >= 12 && hour < 17) return "afternoon";
  if (hour >= 17 && hour < 22) return "evening";
  return "custom";
}

/** Human label for a time preset. */
export function timePresetLabel(preset: TimePreset, t: TFunction): string {
  switch (preset) {
    case "morning":
      return t("automations.time_morning");
    case "afternoon":
      return t("automations.time_afternoon");
    case "evening":
      return t("automations.time_evening");
    case "custom":
      return t("automations.time_custom");
  }
}

/** Format a time as a short locale string, e.g. "9:00 AM". */
export function formatTimeOnly(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

/** Produce a display label for the Time field: preset name or exact time. */
export function describeTime(iso: string, t: TFunction): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const preset = timePresetFromHour(d.getHours());
  if (preset !== "custom") return timePresetLabel(preset, t);
  return formatTimeOnly(iso);
}

/** Apply a time preset to a date, returning a new Date. */
export function applyTimePreset(iso: string, preset: TimePreset): Date {
  const d = new Date(iso);
  const match = TIME_PRESETS.find((p) => p.key === preset);
  if (match) {
    d.setHours(match.hour, match.minute, 0, 0);
  }
  return d;
}

/** Share the automation's prompt + schedule as plain text via the OS share
 * sheet (Messages, Mail, Files, …) — mirrors `shareConversation`. */
export async function shareAutomation(automation: Automation, t: TFunction): Promise<void> {
  const frequencyLabel = t(automationFrequencyMessageKey(automation.frequency));
  const schedule = `${frequencyLabel} · ${formatScheduleAt(automation.next_run_at)}`;
  await presentShareSheet({
    message: `${automation.title ? automation.title + "\n" : ""}${automation.prompt}\n\n${schedule}`,
    title: automation.title || automation.prompt,
  });
}

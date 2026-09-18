import type { TFunction } from "i18next";

import { automationFrequencyMessageKey } from "@/lib/automations/frequency";
import type { Automation } from "@/lib/api/types";
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

/** Share the automation's prompt + schedule as plain text via the OS share
 * sheet (Messages, Mail, Files, …) — mirrors `shareConversation`. */
export async function shareAutomation(automation: Automation, t: TFunction): Promise<void> {
  const frequencyLabel = t(automationFrequencyMessageKey(automation.frequency));
  const schedule = `${frequencyLabel} · ${formatScheduleAt(automation.next_run_at)}`;
  await presentShareSheet({
    message: `${automation.prompt}\n\n${schedule}`,
    title: automation.prompt,
  });
}

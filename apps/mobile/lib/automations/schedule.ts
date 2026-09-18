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

/** A short display title for the task card/detail surface. Automations currently
 * store only the user prompt, so keep this deterministic and presentation-only
 * rather than inventing a second persisted title field. */
export function automationDisplayTitle(prompt: string): string {
  const normalized = prompt.trim().replace(/\s+/g, " ");
  if (!normalized) return "";

  const withoutLead = normalized.replace(
    /^(?:please\s+)?(?:check(?:\s+for)?|search(?:\s+for)?|find|look\s+for|monitor|give\s+me|send\s+me|tell\s+me)\s+/i,
    "",
  );
  const firstClause = (withoutLead.split(/[.;\n]/, 1)[0] || withoutLead).trim();
  const words = firstClause.split(/\s+/).filter(Boolean);
  const clipped = words.slice(0, 7).join(" ");
  const titled = clipped ? clipped.charAt(0).toUpperCase() + clipped.slice(1) : normalized;
  return words.length > 7 ? `${titled}…` : titled;
}

/** Schedule-only label for the middle row on the detail screen. Repeat and time
 * are rendered separately, like ChatGPT Tasks. */
export function formatAutomationScheduleDay(automation: Automation): string {
  const date = new Date(automation.next_run_at);
  if (Number.isNaN(date.getTime())) return "";

  if (automation.frequency === "daily") return date.toLocaleDateString(undefined, { weekday: "long" });
  if (automation.frequency === "weekdays") return date.toLocaleDateString(undefined, { weekday: "long" });
  if (automation.frequency === "weekly") return date.toLocaleDateString(undefined, { weekday: "long" });
  if (automation.frequency === "monthly") {
    return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }
  return date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
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

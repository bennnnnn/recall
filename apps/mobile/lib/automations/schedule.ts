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

const SMALL_TITLE_WORDS = new Set(["a", "an", "and", "at", "for", "in", "of", "on", "or", "the", "to"]);

function titleCase(value: string): string {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .map((word, index) => {
      if (/^[A-Z0-9.]+$/.test(word)) return word;
      const lower = word.toLowerCase();
      if (index > 0 && SMALL_TITLE_WORDS.has(lower)) return lower;
      return lower.charAt(0).toUpperCase() + lower.slice(1);
    })
    .join(" ");
}

/** A short display title for the task card/detail surface. Automations currently
 * store only the user prompt, so this is deterministic presentation logic —
 * not a second source of truth or a hidden generated field. */
export function automationDisplayTitle(prompt: string): string {
  const normalized = prompt.trim().replace(/\s+/g, " ");
  if (!normalized) return "";

  const withoutLead = normalized.replace(
    /^(?:please\s+)?(?:check(?:\s+for)?|search(?:\s+for)?|find|look\s+for|monitor|give\s+me|send\s+me|tell\s+me)\s+/i,
    "",
  );

  if (/\b(?:job postings?|jobs?|openings?|roles?)\b/i.test(withoutLead)) {
    const subject = withoutLead
      .replace(/\b(?:job postings?|jobs?|openings?|roles?)\b[\s\S]*$/i, "")
      .replace(/\b(?:newly\s+active|active|new|matching)\b/gi, "")
      .replace(/\b([a-z0-9]+)-level\b/gi, "$1")
      .replace(/[-–—]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    return subject ? `${titleCase(subject)} Jobs` : "Job Search";
  }

  const firstClause = (withoutLead.split(/[.;\n]/, 1)[0] || withoutLead).trim();
  const words = firstClause.split(/\s+/).filter(Boolean);
  const clipped = words.slice(0, 7).join(" ");
  const titled = titleCase(clipped || normalized);
  return words.length > 7 ? `${titled}…` : titled;
}

/** ChatGPT's detail screen uses compact Repeat values (Daily/Weekly) while
 * list cards use the fuller cadence copy (Every day/Every week). Preserve
 * translated values outside English; only compact the known English labels. */
export function compactFrequencyLabel(label: string): string {
  const normalized = label.trim().toLowerCase();
  if (normalized === "every day") return "Daily";
  if (normalized === "every week") return "Weekly";
  if (normalized === "every month") return "Monthly";
  return label;
}

/** Schedule-only label for the middle row on the detail screen. Repeat and time
 * are rendered separately, like ChatGPT Tasks. */
export function formatAutomationScheduleDay(automation: Automation): string {
  const date = new Date(automation.next_run_at);
  if (Number.isNaN(date.getTime())) return "";

  if (automation.frequency === "weekdays") {
    const monday = new Date(2024, 0, 1);
    const friday = new Date(2024, 0, 5);
    const weekday = new Intl.DateTimeFormat(undefined, { weekday: "long" });
    return `${weekday.format(monday)}–${weekday.format(friday)}`;
  }
  if (automation.frequency === "weekly") {
    return date.toLocaleDateString(undefined, { weekday: "long" });
  }
  if (automation.frequency === "monthly") {
    return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }
  if (automation.frequency === "once") {
    return date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  }
  return "";
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
    title: automationDisplayTitle(automation.prompt),
  });
}

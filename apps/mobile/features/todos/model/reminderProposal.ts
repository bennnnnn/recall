/**
 * A reminder change the chat offers as a card. Nothing is saved until the
 * user taps it; the server then marks the card `"status": "saved"`.
 *
 * ```reminder_proposal {"proposal_id": "…", "tz": "Africa/Nairobi", "items": [{"action": "add",
 *   "title": "Call mom", "due_at": "2026-10-15T18:00:00Z", "repeat": "daily",
 *   "when": "Thursday, Oct 15, 6:00 PM · daily"}]}
 *
 * `tz` is the zone the server read the user's words in (absent on older cards).
 */

import type { RecurrenceRule } from "@/lib/api/types";
import { RECURRENCE_RULES } from "@/lib/api/types";

export type ReminderProposalAction =
  | "add"
  | "complete"
  | "uncheck"
  | "delete"
  | "set_due"
  | "clear_due"
  | "move";

export type ReminderProposalItem = {
  action: ReminderProposalAction;
  title: string;
  dueAt: string | null;
  repeat: RecurrenceRule | null;
  topic: string | null;
  /** The server's own wording of the time, used when `dueAt` does not parse. */
  when: string | null;
};

export type ReminderProposal = {
  proposalId: string;
  items: ReminderProposalItem[];
  saved: boolean;
  /** The IANA zone the card's times were read in, or null on an older card. */
  timeZone: string | null;
};

const ACTIONS = new Set<ReminderProposalAction>([
  "add",
  "complete",
  "uncheck",
  "delete",
  "set_due",
  "clear_due",
  "move",
]);
const FENCE_RE = /```reminder_proposal[ \t]*\n([\s\S]*?)```/gi;
const UNCLOSED_RE = /```reminder_proposal[\s\S]*$/i;

function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function normalizeItem(raw: unknown): ReminderProposalItem | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as Record<string, unknown>;
  const action = row.action as ReminderProposalAction;
  const title = text(row.title);
  if (!ACTIONS.has(action) || !title) return null;
  const repeat = RECURRENCE_RULES.includes(row.repeat as RecurrenceRule)
    ? (row.repeat as RecurrenceRule)
    : null;
  return {
    action,
    title,
    dueAt: text(row.due_at),
    repeat,
    topic: text(row.topic),
    when: text(row.when),
  };
}

function normalizeProposal(raw: unknown): ReminderProposal | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as Record<string, unknown>;
  const proposalId = text(row.proposal_id);
  if (!proposalId || !Array.isArray(row.items)) return null;
  const items = row.items
    .map(normalizeItem)
    .filter((item): item is ReminderProposalItem => item !== null);
  if (items.length === 0) return null;
  return { proposalId, items, saved: row.status === "saved", timeZone: text(row.tz) };
}

export function parseReminderProposals(content: string): ReminderProposal[] {
  if (!content.includes("```reminder_proposal")) return [];
  const proposals: ReminderProposal[] = [];
  for (const match of content.matchAll(new RegExp(FENCE_RE.source, "gi"))) {
    try {
      const parsed = normalizeProposal(JSON.parse(match[1] ?? ""));
      if (parsed) proposals.push(parsed);
    } catch {
      /* a broken card is dropped, not drawn */
    }
  }
  return proposals;
}

export function stripReminderProposalFences(content: string): string {
  if (!content.includes("```reminder_proposal")) return content;
  return content
    .replace(new RegExp(FENCE_RE.source, "gi"), "")
    .replace(UNCLOSED_RE, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

// Cards the user saved this session, so a recycled row or a not yet
// refetched message still reads "Saved".
const savedHere = new Set<string>();

export function markProposalSaved(proposalId: string): void {
  savedHere.add(proposalId);
}

export function isProposalSaved(proposal: ReminderProposal): boolean {
  return proposal.saved || savedHere.has(proposal.proposalId);
}

/** The one action on the card's button: a single change names itself. */
export function proposalAction(proposal: ReminderProposal): ReminderProposalAction | "all" {
  const actions = new Set(proposal.items.map((item) => item.action));
  return actions.size === 1 ? proposal.items[0]!.action : "all";
}

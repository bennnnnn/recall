export type CalendarProposal = {
  proposal_id?: string;
  title: string;
  start_at: string;
  end_at: string;
  location?: string | null;
  description?: string | null;
};

const CALENDAR_PROPOSAL_FENCE_RE = /```calendar_proposal\s*\n([\s\S]*?)```/gi;

function normalizeProposal(raw: unknown): CalendarProposal | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as Record<string, unknown>;
  const title = String(row.title ?? "").trim();
  const start_at = String(row.start_at ?? row.start ?? "").trim();
  const end_at = String(row.end_at ?? row.end ?? "").trim();
  if (!title || !start_at || !end_at) return null;
  const proposal: CalendarProposal = { title, start_at, end_at };
  const proposalId = String(row.proposal_id ?? "").trim();
  if (proposalId) proposal.proposal_id = proposalId;
  const location = String(row.location ?? "").trim();
  if (location) proposal.location = location;
  const description = String(row.description ?? "").trim();
  if (description) proposal.description = description;
  return proposal;
}

export function parseCalendarProposals(content: string): CalendarProposal[] {
  const proposals: CalendarProposal[] = [];
  for (const match of content.matchAll(CALENDAR_PROPOSAL_FENCE_RE)) {
    const raw = match[1]?.trim();
    if (!raw) continue;
    try {
      const parsed = normalizeProposal(JSON.parse(raw));
      if (parsed) proposals.push(parsed);
    } catch {
      /* ignore malformed fences */
    }
  }
  return proposals;
}

export function stripCalendarProposalFences(content: string): string {
  return content.replace(CALENDAR_PROPOSAL_FENCE_RE, "").trimEnd();
}

export function formatProposalWhen(startAt: string, endAt: string): string {
  try {
    const start = new Date(startAt);
    const end = new Date(endAt);
    const date = start.toLocaleDateString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
    const startTime = start.toLocaleTimeString(undefined, {
      hour: "numeric",
      minute: "2-digit",
    });
    const endTime = end.toLocaleTimeString(undefined, {
      hour: "numeric",
      minute: "2-digit",
    });
    return `${date} · ${startTime} – ${endTime}`;
  } catch {
    return `${startAt} – ${endAt}`;
  }
}

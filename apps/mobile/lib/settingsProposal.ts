export type SettingsProposalField =
  | "appearance"
  | "default_model"
  | "response_tone"
  | "locale";

export type SettingsProposalChange = {
  field: SettingsProposalField;
  value: string;
  label: string;
};

export type SettingsProposal = {
  proposal_id: string;
  changes: SettingsProposalChange[];
};

const SETTINGS_PROPOSAL_FENCE_RE = /```settings_proposal\s*\n([\s\S]*?)```/gi;

const FIELDS = new Set<SettingsProposalField>([
  "appearance",
  "default_model",
  "response_tone",
  "locale",
]);

function normalizeChange(raw: unknown): SettingsProposalChange | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as Record<string, unknown>;
  const field = row.field;
  const value = row.value;
  if (typeof field !== "string" || typeof value !== "string") return null;
  if (!FIELDS.has(field as SettingsProposalField)) return null;
  const label = typeof row.label === "string" && row.label.trim() ? row.label : value;
  return { field: field as SettingsProposalField, value, label };
}

function normalizeProposal(raw: unknown): SettingsProposal | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as Record<string, unknown>;
  const proposalId = row.proposal_id;
  if (typeof proposalId !== "string" || !proposalId.trim()) return null;
  const changesRaw = row.changes;
  if (!Array.isArray(changesRaw)) return null;
  const changes = changesRaw
    .map(normalizeChange)
    .filter((item): item is SettingsProposalChange => item !== null);
  if (changes.length === 0) return null;
  return { proposal_id: proposalId, changes };
}

export function parseSettingsProposals(content: string): SettingsProposal[] {
  const proposals: SettingsProposal[] = [];
  const re = new RegExp(SETTINGS_PROPOSAL_FENCE_RE.source, "gi");
  let match: RegExpExecArray | null;
  while ((match = re.exec(content)) !== null) {
    try {
      const parsed = normalizeProposal(JSON.parse(match[1] ?? ""));
      if (parsed) proposals.push(parsed);
    } catch {
      /* skip bad fence */
    }
  }
  return proposals;
}

export function stripSettingsProposalFences(content: string): string {
  return content
    .replace(SETTINGS_PROPOSAL_FENCE_RE, "")
    .replace(/```settings_proposal[\s\S]*$/i, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function hasSettingsProposalFence(content: string): boolean {
  return /```settings_proposal/i.test(content);
}

/** Default topic for app-created todos (lists are chat/LLM only — hidden from UI). */
export const DEFAULT_TOPIC = "General";

const LEGACY_INBOX_TOPIC = "__inbox__";

/** Normalize legacy inbox topics for any chat/display helpers. */
export function normalizeTopic(topic: string): string {
  const trimmed = topic.trim();
  if (!trimmed || trimmed === LEGACY_INBOX_TOPIC) return DEFAULT_TOPIC;
  return trimmed;
}

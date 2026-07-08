import { hasVocabCardFence } from "@/lib/parseVocabCard";
import { hasVocabQuizFence } from "@/lib/parseVocabQuiz";

/** Typical bubble height for FlashList layout hints (variable-height items). */
export const ESTIMATED_MESSAGE_HEIGHT = 88;

/** Delay post-stream rich chrome (sources, full markdown) so layout settles once. */
export const STREAM_LAYOUT_SETTLE_MS = 280;

/** Render keys assigned to the in-flight streaming placeholder (`stream-<ts>`). */
export function isFreshStreamRenderKey(renderKey?: string): boolean {
  return Boolean(renderKey?.startsWith("stream-"));
}

/** Start a timed layout hold; returns an effect cleanup. */
export function beginStreamLayoutHold(setHeld: (held: boolean) => void): () => void {
  setHeld(true);
  const timer = setTimeout(() => setHeld(false), STREAM_LAYOUT_SETTLE_MS);
  return () => clearTimeout(timer);
}

export function shouldHoldStreamLayoutOnPersistedMount(options: {
  isUser: boolean;
  isGenerating: boolean;
  renderKey?: string;
  alreadyApplied: boolean;
}): boolean {
  if (options.isUser || options.isGenerating || options.alreadyApplied) return false;
  return isFreshStreamRenderKey(options.renderKey);
}

const CALENDAR_PROPOSAL_FENCE_RE = /```calendar_proposal/i;

export function messageListItemType(item: {
  id: string;
  role: string;
  content?: string;
}): string {
  if (item.role !== "assistant") return item.role;
  const content = item.content ?? "";
  if (hasVocabQuizFence(content)) return "assistant-quiz";
  if (hasVocabCardFence(content)) return "assistant-vocab";
  if (CALENDAR_PROPOSAL_FENCE_RE.test(content)) return "assistant-calendar";
  return "assistant";
}

export function messageListKey(item: { id: string; renderKey?: string }): string {
  return item.renderKey ?? item.id;
}

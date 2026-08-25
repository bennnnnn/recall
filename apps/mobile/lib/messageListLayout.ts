import { hasVocabCardFence } from "@/lib/parseVocabCard";
import { hasVocabQuizFence } from "@/lib/parseVocabQuiz";
import { hasSettingsProposalFence } from "@/lib/settingsProposal";

/** Typical bubble height for FlashList layout hints (variable-height items). */
export const ESTIMATED_MESSAGE_HEIGHT = 88;

/** Delay post-stream rich chrome (sources, full markdown) so layout settles once. */
export const STREAM_LAYOUT_SETTLE_MS = 280;

/**
 * Keep FlashList native autoscroll off until after chrome + suggestion chips
 * have grown, then JS-pin. Re-arming native at settle (same 280ms as the
 * growth) made two writers fight → spring. 80ms is one frame-or-two after
 * the layout commit, not a second visual hold.
 */
export const STREAM_AUTOSCROLL_RESUME_MS = STREAM_LAYOUT_SETTLE_MS + 80;

/** Render keys assigned to the in-flight streaming placeholder (`stream-<ts>`). */
export function isFreshStreamRenderKey(renderKey?: string): boolean {
  return Boolean(renderKey?.startsWith("stream-"));
}

/** Start a timed layout hold; returns an effect cleanup. */
export function beginStreamLayoutHold(
  setHeld: (held: boolean) => void,
  ms: number = STREAM_LAYOUT_SETTLE_MS,
): () => void {
  setHeld(true);
  const timer = setTimeout(() => setHeld(false), ms);
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
  if (hasSettingsProposalFence(content)) return "assistant-settings";
  return "assistant";
}

export function messageListKey(item: { id: string; renderKey?: string }): string {
  return item.renderKey ?? item.id;
}

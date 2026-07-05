import { hasVocabCardFence } from "@/lib/parseVocabCard";
import { hasVocabQuizFence } from "@/lib/parseVocabQuiz";
import { DAILY_QUIZ_LOADING_ID, hasDailyQuizTextFence, isDailyQuizMessageId } from "@/lib/dailyQuizMessage";

/** Typical bubble height for FlashList layout hints (variable-height items). */
export const ESTIMATED_MESSAGE_HEIGHT = 88;

/** Delay post-stream UI (actions, link previews, sources) so layout settles once. */
export const STREAM_LAYOUT_SETTLE_MS = 280;

const CALENDAR_PROPOSAL_FENCE_RE = /```calendar_proposal/i;

export function messageListItemType(item: {
  id: string;
  role: string;
  content?: string;
}): string {
  if (item.role !== "assistant") return item.role;
  if (item.id === DAILY_QUIZ_LOADING_ID || isDailyQuizMessageId(item.id)) return "assistant-quiz";
  const content = item.content ?? "";
  if (hasVocabQuizFence(content) || hasDailyQuizTextFence(content)) return "assistant-quiz";
  if (hasVocabCardFence(content)) return "assistant-vocab";
  if (CALENDAR_PROPOSAL_FENCE_RE.test(content)) return "assistant-calendar";
  return "assistant";
}

export function messageListKey(item: { id: string; renderKey?: string }): string {
  return item.renderKey ?? item.id;
}

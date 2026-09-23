const VOCAB_CARD_FENCE_RE = /```vocab_card\s*\n([\s\S]*?)```/i;
const VOCAB_CARD_FENCE_PARTIAL_RE = /```vocab_card[\s\S]*$/i;

export function hasVocabCardFence(content: string): boolean {
  return VOCAB_CARD_FENCE_RE.test(content) || VOCAB_CARD_FENCE_PARTIAL_RE.test(content);
}

export function stripVocabCardBlock(content: string): string {
  return content.replace(VOCAB_CARD_FENCE_RE, "").replace(VOCAB_CARD_FENCE_PARTIAL_RE, "").trim();
}

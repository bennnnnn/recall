/** Rough token count — same heuristic as `app.services.context_window.estimate_tokens`. */

const CODE_FENCE_RE = /```[\s\S]*?```/g;

export const DRAFT_TOKEN_HINT_MIN = 80;

export function estimateTokens(text: string): number {
  const stripped = text.trim();
  if (!stripped) return 1;

  const fences = stripped.match(CODE_FENCE_RE) ?? [];
  const denseChars = fences.reduce((sum, block) => sum + block.length, 0);
  const plainLen = Math.max(0, stripped.length - denseChars);
  const words = stripped.split(/\s+/).length;
  const charEst = plainLen / 3.6 + denseChars / 2.5;
  const wordEst = words * 1.35;
  return Math.max(1, Math.trunc(Math.max(charEst, wordEst)));
}

export function shouldShowDraftTokenHint(tokens: number): boolean {
  return tokens >= DRAFT_TOKEN_HINT_MIN;
}

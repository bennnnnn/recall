/**
 * Height policy for the mermaid WebView preview.
 *
 * Extracted so grow/clamp is unit-testable without a linked WebView.
 */

/** Placeholder until the SVG reports its size. */
export const MERMAID_MIN_HEIGHT = 160;
/** Fit a typical ~8-step flowchart TD without clipping. */
export const MERMAID_MAX_HEIGHT = 640;
/** Expanded cap for tall graphs; the WebView scrolls if still taller. */
export const MERMAID_MAX_EXPANDED = 960;
/** Ignore sub-pixel / font-settle chatter so the chat list doesn't bounce. */
export const MERMAID_HEIGHT_EPSILON_PX = 4;

export function clampMermaidPreviewHeight(reported: number, maxHeight: number): number {
  if (!Number.isFinite(reported) || reported <= 0) return MERMAID_MIN_HEIGHT;
  return Math.min(maxHeight, Math.max(MERMAID_MIN_HEIGHT, Math.ceil(reported)));
}

/**
 * Next preview height given a freshly reported SVG height.
 * Grow-only: shrinking after first paint makes the assistant bubble jump.
 * Returns `null` when the height should not change.
 */
export function nextMermaidPreviewHeight(
  reported: number,
  current: number,
  maxHeight: number,
): number | null {
  const next = clampMermaidPreviewHeight(reported, maxHeight);
  if (next <= current + MERMAID_HEIGHT_EPSILON_PX) return null;
  return next;
}

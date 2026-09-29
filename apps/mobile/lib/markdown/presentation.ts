/**
 * Assistant Markdown presentation shared with the API.
 * Boundaries first, then one reasoning state per calculation row.
 */

import { layoutCalculations } from "@/lib/markdown/calculationLayout";
import { repairInlineTokenBoundaries } from "@/lib/markdown/inlineBoundaries";

export function presentAssistantMarkdown(text: string): string {
  if (!text) return text;
  return layoutCalculations(repairInlineTokenBoundaries(text));
}

/** Repair a streaming tail without scanning an open fence body. */
export function presentStreamTail(tail: string): string {
  if (!tail) return tail;
  const fenceAt = tail.indexOf("```");
  const tildeAt = tail.indexOf("~~~");
  const fence =
    fenceAt === -1 ? tildeAt : tildeAt === -1 ? fenceAt : Math.min(fenceAt, tildeAt);
  if (fence === -1) return presentAssistantMarkdown(tail);
  if (fence === 0) return tail;
  return presentAssistantMarkdown(tail.slice(0, fence)) + tail.slice(fence);
}

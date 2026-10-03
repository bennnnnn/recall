/**
 * Assistant Markdown presentation shared with the API.
 * Boundaries first, then one reasoning state per calculation row.
 */

import { layoutCalculations } from "@/lib/markdown/calculationLayout";
import { repairInlineTokenBoundaries } from "@/lib/markdown/inlineBoundaries";
import { normalizeImplicitMath } from "@/lib/math/normalizeImplicit";

export function presentAssistantMarkdown(text: string): string {
  if (!text) return text;
  return layoutCalculations(repairInlineTokenBoundaries(text));
}

/** Same island wrap the settled preprocess uses, outside fences and finished
 * `\(...\)` / `\[...\]` / `$$` spans. Wrapping a line that is already inside
 * those delimiters inserts a second `$` and clips the formula. */
function presentStreamProse(prose: string): string {
  if (!prose) return prose;
  return presentAssistantMarkdown(normalizeImplicitMath(prose));
}

/** Repair a streaming tail without scanning an open fence body. */
export function presentStreamTail(tail: string): string {
  if (!tail) return tail;
  const fenceAt = tail.indexOf("```");
  const tildeAt = tail.indexOf("~~~");
  const fence =
    fenceAt === -1 ? tildeAt : tildeAt === -1 ? fenceAt : Math.min(fenceAt, tildeAt);
  if (fence === -1) return presentStreamProse(tail);
  if (fence === 0) return tail;
  return presentStreamProse(tail.slice(0, fence)) + tail.slice(fence);
}

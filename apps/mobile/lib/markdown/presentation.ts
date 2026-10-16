/**
 * Assistant Markdown presentation, the contract the API applies before a
 * reply is saved (apps/api/app/modules/chat/presentation.py).
 * REPL transcripts become code, then boundaries, then one reasoning state per
 * calculation row. docs/fixtures/presentation_cases.json holds both sides to
 * the same output.
 */

import { layoutCalculations } from "@/lib/markdown/calculationLayout";
import { repairInlineTokenBoundaries } from "@/lib/markdown/inlineBoundaries";
import { readInlineCodeSpan } from "@/lib/markdown/inlineCode";
import { fenceReplTranscripts } from "@/lib/markdown/replTranscript";
import { normalizeImplicitMath } from "@/lib/math/normalizeImplicit";

export function presentAssistantMarkdown(text: string): string {
  if (!text) return text;
  return layoutCalculations(repairInlineTokenBoundaries(fenceReplTranscripts(text)));
}

/** Index of an unclosed `$`, `$$`, `\(`, or `\[`, or null when every opener closed.
 * A dollar inside inline code is code, and an open `$` cannot close past a
 * code span, so it is a lone dollar. */
function openMathStart(prose: string): number | null {
  let inline = false;
  let display = false;
  let paren = false;
  let bracket = false;
  let openAt = -1;
  let i = 0;
  while (i < prose.length) {
    if (prose[i] === "`" && !display && !paren && !bracket) {
      const codeEnd = readInlineCodeSpan(prose, i);
      if (codeEnd != null) {
        inline = false;
        openAt = -1;
        i = codeEnd;
        continue;
      }
    }
    if (prose.startsWith("$$", i)) {
      if (display) {
        display = false;
        openAt = -1;
      } else if (!inline && !paren && !bracket) {
        display = true;
        openAt = i;
      }
      i += 2;
      continue;
    }
    const pair = prose.startsWith("\\(", i)
      ? "paren"
      : prose.startsWith("\\)", i)
        ? "paren-close"
        : prose.startsWith("\\[", i)
          ? "bracket"
          : prose.startsWith("\\]", i)
            ? "bracket-close"
            : null;
    if (pair === "paren" && !inline && !display && !paren && !bracket) {
      paren = true;
      openAt = i;
      i += 2;
      continue;
    }
    if (pair === "paren-close" && paren) {
      paren = false;
      openAt = -1;
      i += 2;
      continue;
    }
    if (pair === "bracket" && !inline && !display && !paren && !bracket) {
      bracket = true;
      openAt = i;
      i += 2;
      continue;
    }
    if (pair === "bracket-close" && bracket) {
      bracket = false;
      openAt = -1;
      i += 2;
      continue;
    }
    if (prose[i] === "$" && !display && !paren && !bracket) {
      if (inline) {
        inline = false;
        openAt = -1;
      } else {
        inline = true;
        openAt = i;
      }
    }
    i += 1;
  }
  return inline || display || paren || bracket ? openAt : null;
}

/** Same island wrap the settled preprocess uses, outside fences and finished
 * `\(...\)` / `\[...\]` / `$$` spans. Wrapping a line that is already inside
 * those delimiters inserts a second `$` and clips the formula. An opener
 * that has not closed yet stays raw so a later token can finish it. */
function presentStreamProse(prose: string): string {
  if (!prose) return prose;
  const openAt = openMathStart(prose);
  const head = openAt == null ? prose : prose.slice(0, openAt);
  const open = openAt == null ? "" : prose.slice(openAt);
  const wrapped = head ? presentAssistantMarkdown(normalizeImplicitMath(head)) : "";
  return wrapped + open;
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

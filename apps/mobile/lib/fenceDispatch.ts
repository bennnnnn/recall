/**
 * Single fence decision for settled render and the open streaming tail.
 *
 * Priority (do not reorder without a table-driven test):
 *   1. Explicit registered structured tag → that fence (never reinterpret)
 *   2. Explicit programming language → code (never a math-answer heuristic)
 *   3. ```json drift → geometry/graph only when the body is that schema
 *   4. Soft langs (untagged / copy / text / plain) → content heuristics
 */

import { shouldUseHtmlPreview } from "@/lib/codeHighlight";
import {
  isExplicitCodeLang,
  looksLikeMathAnswer,
  shouldRenderAsCodeBlock,
  shouldRenderAsCopyBlock,
} from "@/lib/copyBlock";
import {
  type FenceId,
  fenceSpecForLang,
  isMathDiagramLang,
} from "@/lib/fenceRegistry";
import { looksLikeLatexFence, looksLikeMathFenceBody } from "@/lib/math/mathFenceRetag";
import { detectJsonRichFenceKind } from "@/lib/richBlocks";
import {
  isClockFenceBody,
  isDigitalTimeOnly,
  isIanaTimezoneOnly,
} from "@/lib/timeQuestion";

export type FenceRenderKind =
  | "hide"
  | "html"
  | "rich"
  | "answer"
  | "math"
  | "clock"
  | "code"
  | "copy";

export type FenceDecision = {
  kind: FenceRenderKind;
  id?: FenceId;
  lang: string;
};

const DIAGRAM_IDS: ReadonlySet<FenceId> = new Set([
  "geometry",
  "graph",
  "chart",
  "mermaid",
  "chemistry",
  "molecule",
  "molecule3d",
]);

export function isFakeImageGenFence(lang: string): boolean {
  const l = lang.trim().toLowerCase();
  return l === "image" || l === "img" || l === "image-gen" || l === "imagen";
}

/** Untagged / copy / prose tags — the only place content heuristics may run. */
export function allowsContentHeuristic(lang: string): boolean {
  const l = lang.trim().toLowerCase();
  return !l || l === "copy" || l === "text" || l === "plain" || l === "clike";
}

export function classifyFence(lang: string, content: string): FenceDecision {
  const l = lang.trim().toLowerCase();

  if (isFakeImageGenFence(l)) return { kind: "hide", lang: l };
  if (shouldUseHtmlPreview(lang, content)) return { kind: "html", lang: l };

  const spec = fenceSpecForLang(l);
  if (spec?.structured) {
    if (spec.id === "answer") return { kind: "answer", lang: l, id: spec.id };
    if (spec.id === "math") return { kind: "math", lang: l, id: spec.id };
    if (spec.id === "clock") return { kind: "clock", lang: l, id: spec.id };
    return { kind: "rich", lang: l, id: spec.id };
  }

  if (l === "json" || l === "") {
    const jsonKind = detectJsonRichFenceKind(content);
    if (jsonKind === "geometry" || jsonKind === "graph") {
      return { kind: "rich", lang: l, id: jsonKind };
    }
  }

  if (isExplicitCodeLang(lang)) return { kind: "code", lang: l };

  if (allowsContentHeuristic(lang)) {
    if (looksLikeMathAnswer(content)) return { kind: "answer", lang: l };
    if (looksLikeLatexFence(content) || looksLikeMathFenceBody(content)) {
      return { kind: "math", lang: l };
    }
    if (
      isDigitalTimeOnly(content) ||
      isIanaTimezoneOnly(content) ||
      (l === "" && isClockFenceBody(content))
    ) {
      return { kind: "clock", lang: l };
    }
  }

  if (shouldRenderAsCodeBlock(lang, content)) return { kind: "code", lang: l };
  if (shouldRenderAsCopyBlock(lang, content)) return { kind: "copy", lang: l };
  return { kind: "code", lang: l };
}

export type OpenFencePreviewKind = "answer" | "math" | "diagram" | "code" | "hide";

/** Same classifier as settled `renderFence` — preview kinds are a subset. */
export function classifyOpenFencePreview(lang: string, body: string): OpenFencePreviewKind {
  const decision = classifyFence(lang, body);
  if (decision.kind === "answer") return "answer";
  if (decision.kind === "math") return "math";
  // Server already appended 3D after SMILES; the model's extra open
  // ```molecule3d was a pulsing gray box under "3D Structure" that vanished
  // when the fence closed and the leftover was dropped. Hold nothing.
  if (decision.id === "molecule3d") return "hide";
  if (decision.kind === "rich" && decision.id && DIAGRAM_IDS.has(decision.id)) {
    return "diagram";
  }
  if (decision.kind === "clock") return "code";
  return "code";
}

export function shouldPreviewOpenFenceAsAnswer(lang: string, body: string): boolean {
  return classifyOpenFencePreview(lang, body) === "answer";
}

export function shouldPreviewOpenFenceAsMath(lang: string, body: string): boolean {
  return classifyOpenFencePreview(lang, body) === "math";
}

export function looksLikeMathMeta(content: string): boolean {
  return /^(Could not render that diagram\.?|Invalid (graph|geometry) block)/i.test(
    content.trim(),
  );
}

export function shouldHideCopyOnCodeFallback(lang: string, content: string): boolean {
  return looksLikeMathMeta(content) || isMathDiagramLang(lang);
}

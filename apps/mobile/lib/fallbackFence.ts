/**
 * Classify a fenced block for the crash-fallback renderer.
 *
 * When the rich markdown renderer throws, `FallbackMarkdown` renders a
 * best-effort view. Rich fences (callouts, charts, mermaid, math, …) would
 * otherwise show their raw preprocessed markup as monospace code — e.g. a
 * `> [!TIP]` callout becomes a code block literally labelled "callout-tip".
 * Callouts are common and their body is plain prose, so the fallback renders
 * them as a styled prose callout instead of code. Geometry/graph JSON fences
 * still render as native SVG (same as the happy path) — dumping densified
 * point arrays as code is unusable. Other structured fences (chart/mermaid/
 * math/…) stay as styled code blocks — their raw source is at least visible,
 * which is honest degradation.
 */
import { parseGraphSpec } from "@/lib/graphBlock";
import { parseGeometrySpec } from "@/lib/geometryBlock";
import { parseCalloutKind, type CalloutKind } from "@/lib/richBlocks";

export type FallbackFence =
  | { kind: "callout"; calloutKind: CalloutKind; body: string }
  | { kind: "geometry"; body: string }
  | { kind: "graph"; body: string }
  | { kind: "code"; lang: string; code: string };

export function classifyFallbackFence(
  lang: string | undefined,
  content: string,
): FallbackFence {
  const l = (lang || "").trim().toLowerCase();
  const body = content.replace(/\n$/, "").trim();
  if (l.startsWith("callout-") || l === "callout") {
    return { kind: "callout", calloutKind: parseCalloutKind(l), body };
  }
  if (l === "geometry" || (l === "json" && parseGeometrySpec(body))) {
    return { kind: "geometry", body };
  }
  if (l === "graph" || ((l === "json" || l === "") && parseGraphSpec(body))) {
    return { kind: "graph", body };
  }
  return { kind: "code", lang: l, code: body };
}

import { parseGeometrySpec } from "@/lib/geometryBlock";
import { parseGraphSpec } from "@/lib/graphBlock";

/** Model often emits ```json or ```latex — detect and reroute at render time. */
export function looksLikeLatexFence(content: string): boolean {
  const s = content.trim();
  if (!s) return false;
  if (/^\\(?:text|frac|sqrt|pm|times|mathrm|begin|left|right)\b/.test(s)) return true;
  if (/\\text\{/.test(s)) return true;
  return false;
}

export function fenceContentAsGeometry(content: string): boolean {
  return parseGeometrySpec(content) != null;
}

export function fenceContentAsGraph(content: string): boolean {
  return parseGraphSpec(content) != null;
}

/** Rewrite model fences before markdown parse (mirrors vega-lite retagging). */
export function retagMathAndDiagramFences(content: string): string {
  let out = content;

  out = out.replace(/```(?:json)?\s*\n([\s\S]*?)```/gi, (full, body: string) => {
    const trimmed = body.trim();
    if (!trimmed.startsWith("{")) return full;
    if (parseGeometrySpec(trimmed)) {
      return `\`\`\`geometry\n${trimmed}\n\`\`\``;
    }
    if (parseGraphSpec(trimmed)) {
      return `\`\`\`graph\n${trimmed}\n\`\`\``;
    }
    return full;
  });

  out = out.replace(
    /```(?:latex|tex)\s*\n([\s\S]*?)```/gi,
    (_m, body: string) => `\`\`\`math\n${body.trim()}\n\`\`\``,
  );

  out = out.replace(/```\s*\n(\\[\s\S]*?)```/g, (full, body: string) => {
    if (!looksLikeLatexFence(body)) return full;
    return `\`\`\`math\n${body.trim()}\n\`\`\``;
  });

  return out;
}

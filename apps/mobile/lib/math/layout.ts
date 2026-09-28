/**
 * Native math layout. Widths are Computer Modern advances (em fractions),
 * not a flat character count. Fraction bars, radical bars, and accent rules
 * are derived from the child box they cover.
 *
 * Pixels are at the requested `em` (the MathText fontSize). Callers multiply
 * by the device font scale; Text fontSize is left unscaled because React
 * Native applies font scale itself.
 */

import {
  BLACKBOARD_ADVANCE_EM,
  BLACKBOARD_LATIN,
  CDOT_ADVANCE_EM,
  NEGATED_RELATION,
  NORM_ADVANCE_EM,
  PRIME_ADVANCE_EM,
} from "@/lib/math/glyphs";
import { attachScripts, type MathAccentKind, type MathSegment } from "@/lib/math/text";

export const FRAC_SIZE_RATIO = 14 / 16;
export const FRAC_LINE_AT_16 = 18;
export const SQRT_LINE_AT_16 = 20;
export const BODY_LINE_AT_16 = 25;
/** Total vinculum overhang (both sides) as a fraction of the side em. */
export const FRAC_PAD_RATIO = 0.32;
export const SCRIPT_RATIO = 0.7;
export const SCRIPT_RAISE_RATIO = 0.36;
export const SCRIPT_DROP_RATIO = 0.2;
export const RADICAL_LEAD_RATIO = 0.78;
export const RADICAL_OVERHANG_RATIO = 0.1;

export type MathLayout = {
  kind: "row" | "run" | "frac" | "sqrt" | "accent" | "script" | "cancel";
  width: number;
  height: number;
  /** Horizontal margin outside `width` (already included in a parent row). */
  outer: number;
  inkWidth: number;
  children: MathLayout[];
  contentWidth?: number;
  pad?: number;
  lead?: number;
  barStart?: number;
  barEnd?: number;
  bodyWidth?: number;
  bodyHeight?: number;
  bodyTop?: number;
  ruleWidth?: number;
  accentKind?: MathAccentKind;
  /** Positive moves a superscript up. Subscripts use a positive drop. */
  raise?: number;
  drop?: number;
  fontSize?: number;
  lineHeight?: number;
  index?: { left: number; top: number; width: number; fontSize: number; lineHeight: number };
  padLeft?: number;
  /** Space above the first child so a superscript does not leave the box. */
  padTop?: number;
  /** Space below the last child so a subscript does not leave the box. */
  padBottom?: number;
  /** Em used to build this node, when a glyph path must scale with it. */
  em?: number;
  /** The script shift is already inside `height` (stacked exponents). */
  containedShift?: boolean;
  /** Fractional exponent drawn as a miniature stacked fraction. */
  stackedScript?: boolean;
  /** Wide accent (`\widehat`, `\overrightarrow`) whose rule tracks the ink. */
  spanAccent?: boolean;
};

const WIDE = new Set(["m", "w", "M", "W"]);
const NARROW = new Set(["i", "l", "I", "j", "f", "t", "r"]);

function isCombiningMark(ch: string): boolean {
  const c = ch.charCodeAt(0);
  return c >= 0x0300 && c <= 0x036f;
}

/** Em advance for one glyph. Unknown characters still take positive space. */
export function glyphAdvanceEm(ch: string): number {
  if (isCombiningMark(ch)) return 0;
  if (ch === " " || ch === "\u00a0" || ch === "\u2009") return 0.33;
  if (ch >= "0" && ch <= "9") return 0.5;
  if (ch === "m" || ch === "M") return 0.9;
  if (ch === "w" || ch === "W") return 0.85;
  if (WIDE.has(ch)) return 0.8;
  if (NARROW.has(ch)) return 0.32;
  if (/[A-Za-z]/.test(ch)) {
    return ch.toLowerCase() !== ch ? 0.72 : 0.52;
  }
  if (ch === "·" || ch === "⋅") return CDOT_ADVANCE_EM;
  if (ch === "″") return PRIME_ADVANCE_EM * 2;
  if (ch === "‴") return PRIME_ADVANCE_EM * 3;
  if (ch === "‖") return NORM_ADVANCE_EM;
  if (NEGATED_RELATION[ch]) return NEGATED_RELATION[ch].widthEm;
  if (BLACKBOARD_LATIN[ch]) return BLACKBOARD_ADVANCE_EM;
  if (".,:;'`′″‴".includes(ch)) return 0.28;
  if ("()[]{}|/".includes(ch)) return 0.4;
  if ("+-−=<>±∓×÷".includes(ch)) return 0.78;
  const code = ch.codePointAt(0) ?? 0;
  if (code >= 0x370 && code <= 0x3ff) return 0.62;
  if (code > 0x7f) return 0.7;
  return 0.5;
}

export function measureTextWidth(text: string, em: number): number {
  let width = 0;
  for (const ch of text) width += glyphAdvanceEm(ch) * em;
  return width;
}

const OPEN_DELIM = new Set("([{⟨⌈⌊");
const CLOSE_DELIM = new Set(")]}⟩⌉⌋");
const BINARY_OPS = new Set("+−-×÷·⋅±∓");
const RELATION_OPS = new Set("=<>≤≥≠≈∼≡∝→←↔");

/** Em of space to insert around an unspaced operator. Unary minus stays tight. */
function glyphPadEm(
  text: string,
  index: number,
  leadingAtom: boolean,
): { left: number; right: number } {
  const ch = text[index] ?? "";
  const prev = index > 0 ? (text[index - 1] ?? "") : "";
  const next = text[index + 1] ?? "";
  const isRel = RELATION_OPS.has(ch);
  const isBin = BINARY_OPS.has(ch);
  if (!isRel && !isBin) return { left: 0, right: 0 };
  const prevIsAtom = index === 0
    ? leadingAtom
    : prev !== " " && !OPEN_DELIM.has(prev) && !RELATION_OPS.has(prev)
      && !BINARY_OPS.has(prev) && prev !== ",";
  if (isBin && !prevIsAtom) return { left: 0, right: 0 };
  const pad = isRel ? 0.22 : 0.16;
  return {
    left: prevIsAtom && prev !== " " ? pad : 0,
    right: next !== "" && next !== " " && !CLOSE_DELIM.has(next) ? pad : 0,
  };
}

export type OperatorPiece = { text: string; leftEm: number; rightEm: number };

/** Split a run so binary/relation operators can take math space without
 * changing the characters copy and tests read back. */
export function splitOperatorPads(text: string, leadingAtom: boolean): OperatorPiece[] {
  const parts: OperatorPiece[] = [];
  let buf = "";
  for (let i = 0; i < text.length; i += 1) {
    const pad = glyphPadEm(text, i, leadingAtom);
    if (pad.left !== 0 || pad.right !== 0) {
      if (buf) parts.push({ text: buf, leftEm: 0, rightEm: 0 });
      buf = "";
      parts.push({ text: text[i] ?? "", leftEm: pad.left, rightEm: pad.right });
    } else {
      buf += text[i] ?? "";
    }
  }
  if (buf) parts.push({ text: buf, leftEm: 0, rightEm: 0 });
  return parts.length ? parts : [{ text, leftEm: 0, rightEm: 0 }];
}

export function measureRunWidth(text: string, em: number, leadingAtom: boolean): number {
  let width = 0;
  for (const part of splitOperatorPads(text, leadingAtom)) {
    width += measureTextWidth(part.text, em) + (part.leftEm + part.rightEm) * em;
  }
  return width;
}

/** A formula wider than the chat column scrolls; it is not shrunk. */
export const INLINE_SCROLL_GUTTER = 64;

export function inlineMathNeedsScroll(contentWidth: number, windowWidth: number): boolean {
  if (!Number.isFinite(contentWidth) || contentWidth <= 0) return false;
  return contentWidth > Math.max(180, windowWidth - INLINE_SCROLL_GUTTER);
}

function px(at16: number, em: number): number {
  return at16 * (em / 16);
}

function lineHeight(em: number, role: "body" | "frac" | "sqrt"): number {
  if (role === "frac") return px(FRAC_LINE_AT_16, em / FRAC_SIZE_RATIO);
  if (role === "sqrt") return px(SQRT_LINE_AT_16, em);
  return px(BODY_LINE_AT_16, em);
}

function isFractionalScript(value: string): boolean {
  const slash = value.indexOf("/");
  return slash > 0 && slash < value.length - 1 && !value.includes(" ");
}

function scriptExtent(segments: MathSegment[]): { raise: number; drop: number } {
  let raise = 0;
  let drop = 0;
  for (const seg of segments) {
    if (seg.type === "sup" && !isFractionalScript(seg.value)) {
      raise = Math.max(raise, SCRIPT_RAISE_RATIO);
    }
    if (seg.type === "sub") drop = Math.max(drop, SCRIPT_DROP_RATIO);
  }
  return { raise, drop };
}

function measureScript(value: string, em: number, sup: boolean): MathLayout {
  const fontSize = em * SCRIPT_RATIO;
  if (isFractionalScript(value)) {
    const slash = value.indexOf("/");
    const num = measureTextWidth(value.slice(0, slash), fontSize);
    const den = measureTextWidth(value.slice(slash + 1), fontSize);
    const content = Math.max(num, den, fontSize * 0.4);
    const pad = fontSize * 0.28;
    const raise = sup ? em * 0.42 : 0;
    // Two script lines plus the vinculum, then the raise inside the box
    // so the exponent cannot paint outside the measured height.
    const stack = fontSize * 2.45;
    return {
      kind: "script",
      width: content + pad,
      height: stack + raise,
      outer: 0,
      inkWidth: content,
      contentWidth: content,
      pad,
      children: [],
      raise,
      drop: sup ? 0 : em * SCRIPT_DROP_RATIO,
      fontSize,
      lineHeight: fontSize * 1.1,
      stackedScript: true,
      containedShift: true,
    };
  }
  const width = Math.max(measureTextWidth(value, fontSize), value ? fontSize * 0.35 : 0);
  return {
    kind: "script",
    width,
    height: fontSize * 1.15,
    outer: 0,
    inkWidth: width,
    children: [],
    raise: sup ? em * SCRIPT_RAISE_RATIO : 0,
    drop: sup ? 0 : em * SCRIPT_DROP_RATIO,
    fontSize,
    lineHeight: fontSize * 1.15,
    stackedScript: false,
    containedShift: false,
  };
}

function sideMargin(em: number): number {
  return px(3, em);
}

/** Subscript and superscript share one column beside the base. */
function measureScriptColumn(supValue: string, subValue: string, em: number): MathLayout {
  const supNode = measureScript(supValue, em, true);
  const subNode = measureScript(subValue, em, false);
  const width = Math.max(supNode.width, subNode.width, em * 0.35);
  const supBlock = Math.max(supNode.height, supNode.lineHeight ?? 0);
  const subBlock = Math.max(subNode.height, subNode.lineHeight ?? 0);
  const raise = supNode.containedShift ? 0 : (supNode.raise ?? 0);
  const drop = subNode.containedShift ? 0 : (subNode.drop ?? 0);
  return {
    kind: "script",
    width,
    height: raise + supBlock + subBlock + drop,
    outer: 0,
    inkWidth: width,
    children: [supNode, subNode],
    raise: 0,
    drop: 0,
    padTop: raise,
    padBottom: drop,
    containedShift: true,
    stackedScript: false,
  };
}

function measureSegments(
  segments: MathSegment[],
  em: number,
  role: "body" | "frac" | "sqrt",
  inFrac: boolean,
  absorbScripts: boolean,
): MathLayout {
  const children: MathLayout[] = [];
  let width = 0;
  let ink = 0;
  let height = lineHeight(em, role);
  let ascent = 0;
  let descent = 0;
  let leadingAtom = false;
  const pushChild = (child: MathLayout) => {
    children.push(child);
    width += child.width + child.outer;
    ink += child.width;
    height = Math.max(height, child.height);
    if (absorbScripts && !child.containedShift) {
      ascent = Math.max(ascent, child.raise ?? 0);
      descent = Math.max(descent, child.drop ?? 0);
    }
  };
  for (const atom of attachScripts(segments)) {
    pushChild(measureSegment(atom.segment, em, inFrac, leadingAtom));
    if (atom.sup && atom.sub) {
      pushChild(measureScriptColumn(atom.sup.value, atom.sub.value, em));
    }
    leadingAtom = true;
  }
  return {
    kind: "row",
    width,
    height: height + (absorbScripts ? ascent + descent : 0),
    outer: 0,
    inkWidth: ink,
    children,
    padTop: absorbScripts ? ascent : 0,
    padBottom: absorbScripts ? descent : 0,
  };
}

function measureSegment(
  seg: MathSegment,
  em: number,
  inFrac: boolean,
  leadingAtom: boolean,
): MathLayout {
  if (seg.type === "frac") {
    const sideEm = inFrac ? em : em * FRAC_SIZE_RATIO;
    const num = measureSegments(seg.num, sideEm, "frac", true, false);
    const den = measureSegments(seg.den, sideEm, "frac", true, false);
    const numScripts = scriptExtent(seg.num);
    const denScripts = scriptExtent(seg.den);
    const content = Math.max(num.width, den.width, sideEm * 0.45);
    const pad = sideEm * FRAC_PAD_RATIO;
    const gap = Math.max(
      px(3, em),
      sideEm * 0.12,
      sideEm * numScripts.drop,
      sideEm * denScripts.raise,
    );
    const padTop = sideEm * numScripts.raise;
    const padBottom = sideEm * denScripts.drop;
    const bar = 1;
    const margin = sideMargin(em);
    return {
      kind: "frac",
      width: content + pad,
      height: padTop + num.height + den.height + gap * 2 + bar + padBottom,
      outer: margin * 2,
      inkWidth: content,
      contentWidth: content,
      pad,
      padTop,
      padBottom,
      children: [num, den],
    };
  }
  if (seg.type === "sqrt") {
    const body = measureSegments(seg.body, em, "sqrt", inFrac, false);
    const scripts = scriptExtent(seg.body);
    const indexFont = em * 0.55;
    const indexLine = indexFont * 1.15;
    const indexWidth = seg.degree ? measureTextWidth(seg.degree, indexFont) : 0;
    const lead = Math.max(em * RADICAL_LEAD_RATIO, indexWidth + em * 0.42);
    const content = Math.max(body.inkWidth, em * 0.45);
    const inset = body.children.length === 1 ? body.children[0].outer / 2 : 0;
    const overhang = em * RADICAL_OVERHANG_RATIO;
    const barStart = lead + inset - em * 0.04;
    const barEnd = barStart + em * 0.04 + content + overhang;
    const indexHead = seg.degree ? indexLine : 0;
    const bodyTop = indexHead + em * 0.16 + em * scripts.raise;
    const scriptFoot = em * scripts.drop;
    const height = Math.max(px(SQRT_LINE_AT_16, em), body.height + bodyTop + scriptFoot);
    const left = seg.degree ? px(2, em) : px(6, em);
    const right = px(2, em);
    const slot = Math.max(body.width, barEnd - lead);
    return {
      kind: "sqrt",
      width: Math.max(barEnd, lead + slot),
      height,
      outer: left + right,
      inkWidth: content,
      children: [body],
      lead,
      barStart,
      barEnd,
      bodyWidth: content,
      bodyHeight: body.height,
      bodyTop,
      padLeft: left,
      padBottom: scriptFoot,
      em,
      index: seg.degree
        ? {
            left: em * 0.04,
            top: 0,
            width: indexWidth,
            fontSize: indexFont,
            lineHeight: indexLine,
          }
        : undefined,
    };
  }
  if (seg.type === "accent") {
    const body = measureSegments(seg.body, em, inFrac ? "frac" : "body", inFrac, false);
    const scripts = scriptExtent(seg.body);
    const full = seg.kind === "overline" || seg.kind === "underline" || Boolean(seg.span);
    const overhang = seg.kind === "overline" || seg.kind === "underline"
      ? em * 0.04
      : seg.span ? em * 0.02 : 0;
    const ruleWidth = full
      ? body.inkWidth + overhang * 2
      : Math.min(Math.max(body.inkWidth, em * 0.45), em * 0.9);
    const mark = em * 0.22;
    const head = em * scripts.raise;
    const foot = em * scripts.drop;
    return {
      kind: "accent",
      width: Math.max(body.width, ruleWidth),
      height: body.height + mark + head + foot,
      outer: 0,
      inkWidth: body.inkWidth,
      ruleWidth,
      accentKind: seg.kind,
      padTop: head,
      padBottom: foot,
      spanAccent: Boolean(seg.span),
      children: [body],
    };
  }
  if (seg.type === "cancel") {
    const body = measureSegments(seg.body, em, inFrac ? "frac" : "body", inFrac, false);
    return {
      kind: "cancel",
      width: body.width,
      height: body.height,
      outer: 0,
      inkWidth: body.inkWidth,
      children: [body],
    };
  }
  if (seg.type === "sup" || seg.type === "sub") {
    return measureScript(seg.value, em, seg.type === "sup");
  }
  const width = measureRunWidth(seg.value, em, leadingAtom);
  const height = lineHeight(em, inFrac ? "frac" : "body");
  return { kind: "run", width, height, outer: 0, inkWidth: width, children: [] };
}

/** Layout for one MathText formula at `em` CSS pixels (before device font scale). */
export function layoutMath(segments: MathSegment[], em: number): MathLayout {
  return measureSegments(segments, em, "body", false, true);
}

export function radicalStroke(node: MathLayout): { d: string; barLength: number } {
  const em = node.em && node.em > 0 ? node.em : 16;
  const barStart = node.barStart ?? 0;
  const barEnd = node.barEnd ?? node.width;
  const head = node.index ? node.index.lineHeight : 0;
  const hook = Math.max(2, em * 0.16);
  const notch = Math.max(3.2, em * 0.32);
  const top = head + em * 0.05;
  const bottom = Math.max(top + em * 0.45, node.height - em * 0.08);
  const hookY = Math.min(bottom - em * 0.12, head + (node.height - head) * 0.62);
  const d = `M 0 ${hookY} L ${hook * 0.45} ${hookY} L ${notch} ${bottom} L ${barStart} ${top} L ${barEnd} ${top}`;
  return { d, barLength: Math.max(0, barEnd - barStart) };
}

export function walkLayout(node: MathLayout, visit: (node: MathLayout) => void): void {
  visit(node);
  for (const child of node.children) walkLayout(child, visit);
}

export function findLayouts(node: MathLayout, kind: MathLayout["kind"]): MathLayout[] {
  const found: MathLayout[] = [];
  walkLayout(node, (item) => {
    if (item.kind === kind) found.push(item);
  });
  return found;
}

/** Layout rules shared by tests and any future debug overlay. */
export function layoutProblems(node: MathLayout, em: number): string[] {
  const problems: string[] = [];
  walkLayout(node, (item) => {
    if (!Number.isFinite(item.width) || !Number.isFinite(item.height)) {
      problems.push(`${item.kind} has a non-finite box`);
    }
    if (item.width < 0 || item.height < 0 || item.outer < 0) {
      problems.push(`${item.kind} has a negative dimension`);
    }
    for (const child of item.children) {
      if (child.width - item.width > 1 && item.kind !== "row") {
        problems.push(`${child.kind} is wider than its ${item.kind} parent`);
      }
    }
    if (item.kind === "sqrt" && item.bodyWidth != null && item.barStart != null && item.barEnd != null) {
      const bar = item.barEnd - item.barStart;
      const extra = bar - item.bodyWidth;
      if (extra < -0.5 || extra > em * 0.28) {
        problems.push(`radical bar ${bar.toFixed(2)} vs radicand ${item.bodyWidth.toFixed(2)}`);
      }
      const strokeEm = item.em && item.em > 0 ? item.em : em;
      if (item.barStart < strokeEm * 0.25) {
        problems.push("radical bar starts inside the hook");
      }
      if (item.index && item.bodyTop != null) {
        const indexBottom = item.index.top + item.index.lineHeight;
        if (indexBottom - item.bodyTop > 0.5) {
          problems.push("root index overlaps the radicand");
        }
      }
    }
    if (item.kind === "frac" && item.contentWidth != null && item.pad != null) {
      if (item.width + 0.01 < item.contentWidth) {
        problems.push("fraction bar shorter than its content");
      }
      if (item.pad > em * 0.5) problems.push("fraction pad is too wide");
      const [num, den] = item.children;
      const head = item.padTop ?? 0;
      const foot = item.padBottom ?? 0;
      if (num && den && item.height + 0.01 < head + num.height + den.height + foot) {
        problems.push("denominator overlaps the fraction bar");
      }
    }
    if (
      item.kind === "accent"
      && (item.accentKind === "overline" || item.accentKind === "underline" || item.spanAccent)
    ) {
      const rule = item.ruleWidth ?? 0;
      const extra = Math.abs(rule - item.inkWidth);
      if (extra > em * 0.2) {
        problems.push(`overline rule ${rule.toFixed(2)} vs ink ${item.inkWidth.toFixed(2)}`);
      }
    }
    if (item.kind === "script" && item.fontSize != null && item.inkWidth > 0) {
      if (item.fontSize > em * 0.8) problems.push("script uses body size");
      if ((item.raise ?? 0) <= 0 && (item.drop ?? 0) <= 0) {
        problems.push("script sits on the baseline");
      }
    }
  });
  return problems;
}

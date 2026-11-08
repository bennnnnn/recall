/**
 * How wide a native formula is drawn, without a device. Each glyph takes the advance its
 * face carries (KaTeX's own font metrics, the numbers in the bundled KaTeX TTFs), a glyph
 * run is its glyphs plus its padding, a sized piece (a fraction, a root, a script column)
 * is its width plus its margins, and a box is its pieces in a row, or its `width` or
 * `minWidth` when that is set. A box wider than its pieces is empty room after its last
 * glyph, which a reader sees as a space before the mark that follows ("15 m/s ?").
 */
import { StyleSheet } from "react-native";

// The components project has no Node types (see lib/__tests__/licenses.test.ts).
declare const __dirname: string;
const { readFileSync } = jest.requireActual<{ readFileSync(path: string, encoding: "utf8"): string }>("node:fs");
const { join } = jest.requireActual<{ join(...parts: string[]): string }>("node:path");

type Style = Record<string, unknown>;
/** A rendered host element, or a node of `toJSON()`. */
export type Element = { type: unknown; props: Record<string, unknown>; children: (Element | string)[] | null };
type Face = { family: string; size: number };

/** The faces MathText paints in, as KaTeX names their metrics. */
const METRICS_FACE: Record<string, string> = {
  KaTeX_Main: "Main-Regular",
  KaTeX_MathItalic: "Math-Italic",
  KaTeX_AMS: "AMS-Regular",
  KaTeX_Size1: "Size1-Regular",
};

/** The empty run a formula sets its baseline with draws nothing. */
const ZERO_WIDTH = new Set([0x200b]);

let metrics: Record<string, Record<string, number[]>> | null = null;

function advances(): Record<string, Record<string, number[]>> {
  if (metrics) return metrics;
  // An ES module jest does not transform; its body is an object literal with trailing commas.
  const file = join(__dirname, "..", "..", "..", "node_modules", "katex", "src", "fontMetricsData.js");
  const source = readFileSync(file, "utf8");
  const body = source.slice(source.indexOf("{"), source.lastIndexOf("}") + 1).replace(/,(\s*[}\]])/g, "$1");
  metrics = JSON.parse(body) as Record<string, Record<string, number[]>>;
  return metrics;
}

function styleOf(node: Element): Style {
  return (StyleSheet.flatten(node.props.style as object) ?? {}) as Style;
}

function num(value: unknown): number {
  return typeof value === "number" ? value : 0;
}

/** The first of the keys a style sets, as React Native reads `marginLeft` over `marginHorizontal` over `margin`. */
function first(style: Style, keys: string[]): number {
  const key = keys.find((name) => typeof style[name] === "number");
  return key ? num(style[key]) : 0;
}

function horizontal(style: Style, side: "margin" | "padding"): number {
  return first(style, [`${side}Left`, `${side}Horizontal`, side])
    + first(style, [`${side}Right`, `${side}Horizontal`, side]);
}

function glyphsWidth(text: string, face: Face): number {
  const table = advances()[METRICS_FACE[face.family] ?? ""];
  if (!table) throw new Error(`no metrics for face ${face.family}`);
  let width = 0;
  for (const ch of text) {
    const code = ch.codePointAt(0) ?? 0;
    if (ZERO_WIDTH.has(code)) continue;
    const advance = table[String(code)]?.[4];
    if (advance === undefined) throw new Error(`${face.family} has no ${JSON.stringify(ch)}`);
    width += advance * face.size;
  }
  return width;
}

/** A Text and the Text nested in it: glyphs in the face each one sets, plus padding. */
function textWidth(node: Element, inherited: Face): number {
  const style = styleOf(node);
  const face = {
    family: typeof style.fontFamily === "string" ? style.fontFamily : inherited.family,
    size: typeof style.fontSize === "number" ? style.fontSize : inherited.size,
  };
  let width = horizontal(style, "padding");
  for (const child of node.children ?? []) {
    width += typeof child === "string" ? glyphsWidth(child, face) : textWidth(child, face);
  }
  return width;
}

/** The width a piece takes in its row, its margins included. */
function pieceWidth(node: Element): number {
  const style = styleOf(node);
  const own = node.type === "Text"
    ? textWidth(node, { family: "", size: 0 })
    : typeof style.width === "number" ? style.width : drawnBox(node).box;
  return own + horizontal(style, "margin");
}

/**
 * A View's drawn width (`box`) beside the width of what it holds (`ink`), both in layout
 * pixels. A row holds its pieces side by side, a column its widest one.
 */
export function drawnBox(view: Element): { box: number; ink: number } {
  const style = styleOf(view);
  const pieces = (view.children ?? []).filter((child): child is Element => typeof child !== "string").map(pieceWidth);
  const content = style.flexDirection === "row"
    ? pieces.reduce((sum, width) => sum + width, 0)
    : Math.max(0, ...pieces);
  const ink = content + horizontal(style, "padding");
  const sized = typeof style.width === "number" ? style.width : ink;
  return { box: Math.max(sized, num(style.minWidth)), ink };
}

/** Room after a formula's glyphs a reader sees as a space; less is the pixel grid. */
const VISIBLE_ROOM = 0.5;

const SUBSCRIPT = "₀₁₂₃₄₅₆₇₈₉";
const SUPERSCRIPT = "⁰¹²³⁴⁵⁶⁷⁸⁹";

function shiftOf(style: Style): number {
  const steps = Array.isArray(style.transform) ? (style.transform as { translateY?: unknown }[]) : [];
  return num(steps.find((step) => typeof step.translateY === "number")?.translateY);
}

/**
 * A line as a reader sees it: the glyphs, a dropped script as a subscript and a raised
 * one as a superscript, and a space wherever an item keeps a word gap after it or a
 * formula's box runs on past its glyphs.
 */
export function readLine(node: Element | string | null): string {
  if (node == null) return "";
  if (typeof node === "string") return node.replace(/\u00a0/g, " ").replace(/\u200b/g, "");
  const style = styleOf(node);
  let text = (node.children ?? []).map(readLine).join("");
  if (node.props.testID === "math-script") {
    const digits = shiftOf(style) > 0 ? SUBSCRIPT : SUPERSCRIPT;
    text = Array.from(text, (ch) => (/\d/.test(ch) ? digits[Number(ch)] : ch)).join("");
  }
  if (node.props.testID === "math-text-tall") {
    const { box, ink } = drawnBox(node);
    if (box - ink > VISIBLE_ROOM) text += " ";
  }
  if (num(style.marginLeft) > 0) text = ` ${text}`;
  if (num(style.marginRight) > 0) text += " ";
  return text;
}

/**
 * A formula's box: no `width` cap and no `minWidth` floor, so it is as wide as what it
 * draws, and the laid-out height. A box of fractions and roots alone draws their laid-out
 * widths, so its `width` is the layout's; `widerThan` is a column it must scroll past.
 */
export function expectFormulaBox(
  node: unknown,
  size: { width?: number; height?: number; widerThan?: number },
): void {
  const element = node as Element;
  const style = styleOf(element);
  expect(style.width).toBeUndefined();
  expect(style.minWidth).toBeUndefined();
  if (size.height !== undefined) expect(style.height).toBeCloseTo(size.height, 5);
  const { box, ink } = drawnBox(element);
  expect(box).toBeCloseTo(ink, 1);
  if (size.width !== undefined) expect(box).toBeCloseTo(size.width, 5);
  if (size.widerThan !== undefined) expect(box).toBeGreaterThan(size.widerThan);
}

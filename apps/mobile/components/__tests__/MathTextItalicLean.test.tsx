/**
 * An italic letter's ink leans past its advance, and a Text box that ends on one cut the
 * lean off: `P` drew as `F` in the composer, and again in a worked reply's grey "where $P$ =
 * original price" line (2026-11-12). Every box a formula draws keeps its last italic
 * letter's ink: the room is its italic correction (KaTeX's own metric, so V and Y get more
 * than P), given back as a negative margin so nothing beside it moves. Nested in a
 * sentence's Text a formula is no box, and the words after it are its room.
 */
import type { ReactElement } from "react";
import { Dimensions, StyleSheet, Text, View } from "react-native";
import { render } from "@testing-library/react-native";
import type { JsonNode } from "test-renderer";

import { MarkdownContent } from "@/components/MarkdownContent";
import { InlineFlow } from "@/components/markdown/rules/inlineFlow";
import { MathText } from "@/components/rich/MathText";
import { AnswerBlock } from "@/components/rich/AnswerBlock";
import { MathDraftPreview } from "@/features/chat/components/MathDraftPreview";
import { endsOnItalicLetter, italicCorrectionEm, italicLeanEm, latexLeanEm } from "@/lib/math/glyphs";
import { FRAC_SIZE_RATIO, layoutMath, measureTextWidth } from "@/lib/math/layout";
import { parseSimpleLatex } from "@/lib/math/text";
import { Type } from "@/lib/type";

jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("@/components/LinkPreviewCard", () => ({ LinkPreviewCard: () => null }));
jest.mock("@/components/rich/MathSvgView", () => ({ MathSvgView: () => null }));
jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  writeAsStringAsync: jest.fn(),
  EncodingType: { UTF8: "utf8" },
}));

type Edge = { text: string; padding: number; margin: number };

/** Every Text drawn, in tree order: its glyphs, its right padding and its right margin. */
async function edgesOf(element: ReactElement): Promise<Edge[]> {
  const screen = await render(element);
  const edges: Edge[] = [];
  const glyphs = (node: JsonNode | string): string =>
    typeof node === "string" ? node : (node.children ?? []).map(glyphs).join("");
  const walk = (node: JsonNode | string | null) => {
    if (!node || typeof node === "string") return;
    if (node.type === "Text") {
      const style = StyleSheet.flatten(node.props.style) ?? {};
      const number = (value: unknown) => (typeof value === "number" ? value : 0);
      edges.push({ text: glyphs(node), padding: number(style.paddingRight), margin: number(style.marginRight) });
    }
    node.children?.forEach(walk);
  };
  const tree = screen.toJSON();
  (Array.isArray(tree) ? tree : [tree]).forEach(walk);
  return edges;
}

/** The Text whose glyphs are exactly `text`. */
function edgeOf(edges: Edge[], text: string): Edge {
  const found = edges.find((edge) => edge.text.replace(/​/g, "") === text);
  if (!found) throw new Error(`no Text ${JSON.stringify(text)} in ${JSON.stringify(edges)}`);
  return found;
}

// The components project has no Node types (see lib/__tests__/licenses.test.ts).
declare const __dirname: string;

const leanAt = (letter: string, size: number) => italicCorrectionEm(letter) * size;
const draftEdges = (input: string) => edgesOf(<MathDraftPreview input={input} showCaret={false} />);

beforeEach(() => {
  jest.spyOn(Dimensions, "get").mockReturnValue({ width: 390, height: 844, scale: 3, fontScale: 1 });
});

afterEach(() => jest.restoreAllMocks());

describe("how far a letter leans", () => {
  it.each([
    ["P", true],
    ["x+V", true],
    ["Φ", true],
    ["x^{2}", false],
    ["5", false],
    [String.raw`\sin`, false],
    ["P ", false],
  ])("reads whether %j ends on an italic letter", (value, italic) => {
    expect(endsOnItalicLetter(value)).toBe(italic);
  });

  it.each([
    ["P", 0.139],
    ["x+V", 0.222],
    ["Y", 0.222],
    ["T", 0.139],
    ["x", 0],
    ["5", 0],
    ["sin", 0],
  ])("leans %j by its italic correction", (value, em) => {
    expect(italicLeanEm(value)).toBeCloseTo(em, 3);
  });

  it("takes KaTeX's own italic correction for every letter of the italic face", () => {
    // fontMetricsData rows are [depth, height, italic, skew, width] by code point.
    const { readFileSync } = jest.requireActual<{ readFileSync(path: string, encoding: "utf8"): string }>("node:fs");
    const { join } = jest.requireActual<{ join(...parts: string[]): string }>("node:path");
    const file = join(__dirname, "..", "..", "node_modules", "katex", "src", "fontMetricsData.js");
    const source = readFileSync(file, "utf8");
    const body = source.slice(source.indexOf("{"), source.lastIndexOf("}") + 1).replace(/,(\s*[}\]])/g, "$1");
    const italic = (JSON.parse(body) as Record<string, Record<string, number[]>>)["Math-Italic"]!;
    const letters = Object.entries(italic).filter(([code]) => /[A-Za-zͰ-Ͽ]/.test(String.fromCodePoint(Number(code))));
    expect(letters.length).toBeGreaterThan(80);
    for (const [code, metrics] of letters) {
      expect([String.fromCodePoint(Number(code)), italicCorrectionEm(String.fromCodePoint(Number(code)))])
        .toEqual([String.fromCodePoint(Number(code)), expect.closeTo(metrics[2]!, 3)]);
    }
  });
});

describe("a formula that is a box of its own", () => {
  // The capitals that lean furthest, at a note's size, a reply's and a heading's.
  const cases = ["P", "F", "T", "V", "W", "Y"].flatMap((letter) =>
    [Type.secondary.fontSize, 18, 22].map((size) => [letter, size] as const),
  );

  it.each(cases)("keeps the ink of %s at %dpx and moves nothing beside it", async (letter, size) => {
    const edge = edgeOf(await edgesOf(<View><MathText latex={letter} fontSize={size} /></View>), letter);
    expect(edge.padding).toBeCloseTo(leanAt(letter, size), 5);
    expect(edge.padding + edge.margin).toBeCloseTo(0, 5);
  });

  it("keeps the ink of a letter that ends a box inside a formula", async () => {
    const edges = await edgesOf(<View><MathText latex={String.raw`P\frac{1}{V} + T_{1} + v_{f}`} /></View>);
    // P before a fraction, a fraction's denominator, a base before its script (v leans a
    // little too), the script.
    const kept = edges.filter((edge) => edge.margin < 0);
    expect(kept.map((edge) => edge.text.trim().at(-1))).toEqual(["P", "V", "T", "v", "f"]);
    for (const edge of kept) expect(edge.padding + edge.margin).toBeCloseTo(0, 5);
    expect(kept[0]!.padding).toBeCloseTo(leanAt("P", 16), 5);
    expect(kept[1]!.padding).toBeCloseTo(leanAt("V", 16 * FRAC_SIZE_RATIO), 5);
    expect(kept[2]!.padding).toBeCloseTo(leanAt("T", 16), 5);
  });

  // TeX sets a superscript after its base's lean and a subscript at the advance (local
  // review, 2026-11-12: V's lean drawn without that room ran into its exponent).
  it.each(["V^{2}", "T^{2}", "P^{2}", "W^{3}", "f^{2}", "T_{1}^{2}"])(
    "gives the base of %s real room before its superscript, as the layout measures it",
    async (latex) => {
      const letter = latex[0]!;
      const edge = edgeOf(await edgesOf(<View><MathText latex={latex} /></View>), letter);
      expect(edge).toMatchObject({ padding: expect.closeTo(leanAt(letter, 16), 5), margin: 0 });
      const base = layoutMath(parseSimpleLatex(latex), 16).children[0]!;
      expect(base.width).toBeCloseTo(measureTextWidth(letter, 16) + leanAt(letter, 16), 5);
    },
  );

  it.each(["v_{f}", "T_{1}", "P_{0}"])("sets the subscript of %s at the base's advance", async (latex) => {
    const letter = latex[0]!;
    const edge = edgeOf(await edgesOf(<View><MathText latex={latex} /></View>), letter);
    expect(edge.padding + edge.margin).toBeCloseTo(0, 5);
    const base = layoutMath(parseSimpleLatex(latex), 16).children[0]!;
    expect(base.width).toBeCloseTo(measureTextWidth(letter, 16), 5);
  });

  it("ends a stacked formula on a whole letter", async () => {
    const edge = edgeOf(await edgesOf(<View><MathText latex={String.raw`\frac{1}{2}P`} /></View>), "P");
    expect(edge.padding).toBeCloseTo(leanAt("P", 16), 5);
    expect(edge.padding + edge.margin).toBeCloseTo(0, 5);
  });

  it("keeps real room in a scroll, whose viewport ends where the formula does", async () => {
    const edge = edgeOf(await edgesOf(<View><MathText scrollOverflow latex={String.raw`\frac{1}{2}P`} /></View>), "P");
    expect(edge).toMatchObject({ padding: expect.closeTo(leanAt("P", 16), 5), margin: 0 });
  });

  it.each(["x^{2}", "5", String.raw`\sin(x)`, String.raw`3\,\mathrm{kg}`, "P = 400"])(
    "adds nothing after %s, which ends on no leaning letter",
    async (latex) => {
      const edges = await edgesOf(<View><MathText latex={latex} /></View>);
      expect(edges.filter((edge) => edge.margin < 0)).toEqual([]);
    },
  );

  it("keeps the P of a worked reply's where-line whole (2026-11-12)", async () => {
    const reply = "**Given**  \n$P = 400\\,\\mathrm{Birr}$  \n$r_d = 0.15$  \nwhere $P$ = original price, $r_d$ = discount rate";
    const edges = await edgesOf(<MarkdownContent content={reply} />);
    const noteSize = Type.secondary.fontSize;
    const named = edges.filter((edge) => edge.text.replace(/​/g, "") === "P" && edge.padding > 0);
    expect(named).toHaveLength(1);
    expect(named[0]!.padding).toBeCloseTo(leanAt("P", noteSize), 5);
    expect(named[0]!.padding + named[0]!.margin).toBeCloseTo(0, 5);
  });
});

describe("a formula nested in a sentence's Text", () => {
  it.each(["P", "V", String.raw`x + Y`])("draws %s with no edge: the words after it are its room", async (latex) => {
    const edges = await edgesOf(<Text>where <MathText latex={latex} /> is the power</Text>);
    expect(edges.filter((edge) => edge.padding > 0 || edge.margin !== 0)).toEqual([]);
  });
});

describe("a formula last in a word of a paragraph's flow", () => {
  // A paragraph holding a fraction flows word by word; `$P$` and its gap are one Text there.
  it("keeps the ink of its letter out of the gap after it, which stays as wide", async () => {
    const edges = await edgesOf(
      <InlineFlow>
        <Text>Half is </Text>
        <MathText latex={String.raw`\frac{1}{2}`} fontSize={18} />
        <Text>, where </Text>
        <MathText latex="P" fontSize={18} />
        <Text> is the power.</Text>
      </InlineFlow>,
    );
    const unit = edges.find((edge) => edge.text.replace(/\u200b/g, "") === "P" && edge.padding > 0);
    expect(unit?.padding).toBeCloseTo(leanAt("P", 18), 5);
    const gap = edges.find((edge) => edge.text === "where")!;
    expect(unit!.padding + unit!.margin).toBeCloseTo(gap.margin, 5);
  });
});

describe("the composer's italic lean", () => {
  it.each([
    ["$P(5,2)$", "P"],
    ["$x+P$", "P"],
    ["Solve $P$ now", "P"],
    ["$x+V$", "V"],
  ])("gives the letter that ends a piece of %s real room", async (input, letter) => {
    const edges = await draftEdges(input);
    const leaning = edges.filter((edge) => edge.padding > 0 && edge.margin === 0);
    expect(leaning.map((edge) => edge.padding)).toContainEqual(expect.closeTo(leanAt(letter, 16), 5));
  });

  it.each(["$x^{2}$", "$x_{1}$", "$a_{n}$", "$2x^{2}$", "$P_{1}$", "$T_{0}$"])(
    "sets the script of %s against its letter",
    async (input) => {
      const edges = await draftEdges(input);
      expect(edges.filter((edge) => edge.margin === 0 && edge.padding > 0)).toEqual([]);
    },
  );

  it.each([
    ["$T^{2}$", "T"],
    ["$V^{2}$", "V"],
    ["$P^{n}$", "P"],
  ])("sets the superscript of %s after its letter's lean", async (input, letter) => {
    const edges = await draftEdges(input);
    const leaning = edges.filter((edge) => edge.padding > 0 && edge.margin === 0);
    expect(leaning.map((edge) => edge.padding)).toEqual([expect.closeTo(leanAt(letter, 16), 5)]);
  });

  it.each(["$x^{n}$", String.raw`$\frac{x}{y}$`, String.raw`$\sqrt{P}$`, String.raw`$\frac{x^{2}}{y}$`, "$(x)$"])(
    "leans no letter inside a box of %s",
    async (input) => {
      const edges = await draftEdges(input);
      expect(edges.filter((edge) => edge.margin === 0 && edge.padding > 0)).toEqual([]);
    },
  );
});

describe("a Text that holds a formula last", () => {
  // An answer card draws its value as a Text holding the formula (`P = IV` lost the right
  // of its V): that Text keeps the ink, and moves nothing.
  it.each([
    ["P = IV", "V"],
    ["P = 5\\,\\mathrm{W} \\text{ or } Y", "Y"],
  ])("keeps the last letter of the answer %s whole", async (content, letter) => {
    const edges = await edgesOf(<AnswerBlock content={content} />);
    const host = edges.find((edge) => edge.margin < 0);
    expect(host).toMatchObject({ padding: expect.closeTo(leanAt(letter, 20), 5) });
    expect(host!.padding + host!.margin).toBeCloseTo(0, 5);
  });

  it.each([
    ["P = IV", 0.222],
    [String.raw`x = \alpha`, 0],
    [String.raw`5\,\mathrm{kg}`, 0],
    ["x^{2}", 0],
    [String.raw`a \sin`, 0],
  ])("reads how far %s leans from its TeX", (latex, em) => {
    expect(latexLeanEm(latex)).toBeCloseTo(em, 3);
  });
});

describe("a React Native without TextAncestorContext", () => {
  // The export is unstable: without it, useContext(undefined) would throw in every formula.
  it("still draws a formula, as a box of its own", async () => {
    let drawn: unknown = null;
    await jest.isolateModulesAsync(async () => {
      jest.doMock("react-native", () => {
        const actual = jest.requireActual<Record<string, unknown>>("react-native");
        return new Proxy(actual, {
          get: (target, key) => (key === "unstable_TextAncestorContext" ? undefined : target[key as string]),
        });
      });
      /* eslint-disable @typescript-eslint/no-require-imports -- loaded in the sandbox without the export */
      const React = require("react");
      const RN = require("react-native");
      const { MathText: Isolated } = require("@/components/rich/MathText");
      const { createRoot } = require("test-renderer");
      /* eslint-enable @typescript-eslint/no-require-imports */
      expect(RN.unstable_TextAncestorContext).toBeUndefined();
      const root = createRoot();
      await React.act(async () => root.render(React.createElement(RN.View, null, React.createElement(Isolated, { latex: "P" }))));
      drawn = root.container.children.length;
    });
    expect(drawn).toBe(1);
  });
});

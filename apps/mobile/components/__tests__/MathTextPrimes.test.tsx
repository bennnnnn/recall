import { StyleSheet, type StyleProp, type TextStyle } from "react-native";
import { render } from "@testing-library/react-native";

import { MathText } from "@/components/rich/MathText";
import { SCRIPT_RATIO } from "@/lib/math/layout";
import { formulaText, spokenFormula } from "@/lib/math/text";
import type { Element } from "./support/mathInk";

/** Every drawn Text whose own strings hold a prime glyph. */
function primeTexts(node: Element | (Element | string)[] | string | null): Element[] {
  if (node == null || typeof node === "string") return [];
  if (Array.isArray(node)) return node.flatMap(primeTexts);
  const own = (node.children ?? []).filter((child): child is string => typeof child === "string").join("");
  const here = node.type === "Text" && /[′″‴]/.test(own) ? [node] : [];
  return [...here, ...primeTexts(node.children ?? [])];
}

function ownText(node: Element): string {
  return (node.children ?? []).filter((child) => typeof child === "string").join("");
}

describe("MathText primes", () => {
  // A prime is a superscript in TeX (f' is f^{\prime}). The face's prime is cut to sit raised
  // at script size; drawn on the baseline at full size it read as a slash, f″ as "f//".
  it.each([
    ["f'(x)", ["′"]],
    ["f''(x) = 6x+6", ["′′"]],
    ["f'''(x)", ["′′′"]],
    ["y'", ["′"]],
    ["f'(2) = 0", ["′"]],
    [String.raw`(f \circ g)'(x)`, ["′"]],
    ["2' 30''", ["′", "′′"]],
    ["x' y'", ["′", "′"]],
    ["f′(x) + g″(x)", ["′", "′′"]],
    [String.raw`f^{\prime}(x)`, ["′"]],
    [String.raw`30^{\circ}15′`, ["′"]],
    [String.raw`\frac{f'(x)}{g(x)}`, ["′"]],
  ])("raises %s's primes at script size", async (latex, primes) => {
    const screen = await render(<MathText latex={latex} fontSize={16} />);
    const drawn = primeTexts(screen.toJSON() as Element | null);
    expect(drawn.map(ownText)).toEqual(primes);
    for (const node of drawn) {
      expect(node.props.testID).toBe("math-script");
      expect((StyleSheet.flatten(node.props.style as StyleProp<TextStyle>) ?? {}).fontSize).toBeLessThanOrEqual(16 * SCRIPT_RATIO);
    }
  });

  it.each([
    String.raw`\text{don't stop}`,
    "AB'",
    "it's",
  ])("leaves the apostrophe in %s as it was written", async (latex) => {
    const screen = await render(<MathText latex={latex} fontSize={16} />);
    expect(primeTexts(screen.toJSON() as Element | null)).toEqual([]);
    expect(screen.queryAllByTestId("math-script")).toEqual([]);
  });

  it.each([
    ["f''(x) = 6x+6", "f″(x) = 6x+6"],
    [String.raw`f^{\prime}(2)`, "f′(2)"],
    ["2' 30''", "2′ 30″"],
  ])("copies and reads %s with its primes, never as a power", (latex, text) => {
    expect(formulaText(latex)).toBe(text);
    expect(spokenFormula(latex)).toBe(text);
  });
});

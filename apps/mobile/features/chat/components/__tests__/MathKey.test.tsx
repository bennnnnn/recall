import { StyleSheet } from "react-native";
import { render } from "@testing-library/react-native";

import {
  KEY_FONT_SCALE_MAX,
  MathKey,
  keyLabelRuns,
  keyLabelSegments,
  keyLabelSize,
} from "@/features/chat/components/MathKey";
import { MATH_FONT, MATH_SIZE1_FONT, MATH_SYMBOL_FONT, MATH_VARIABLE_FONT } from "@/lib/fonts";
import { UI_FONT_FAMILY } from "@/lib/uiFont";

describe("math key labels", () => {
  it("draws scripts as raised and lowered text, not Unicode the face may lack", () => {
    expect(keyLabelSegments("sin^{−1}")).toEqual([
      { text: "sin", script: "base" },
      { text: "−1", script: "sup" },
    ]);
    expect(keyLabelSegments("log_{n}")).toEqual([
      { text: "log", script: "base" },
      { text: "n", script: "sub" },
    ]);
    expect(keyLabelSegments("d^{2}/dx^{2}").map((seg) => seg.script)).toEqual([
      "base",
      "sup",
      "base",
      "sup",
    ]);
  });

  it("puts each glyph in a bundled face that has it", () => {
    expect(keyLabelRuns("sin", false)).toEqual([{ text: "sin", family: UI_FONT_FAMILY, scale: 1 }]);
    expect(keyLabelRuns("∬", false)[0]!.family).toBe(MATH_SIZE1_FONT);
    expect(keyLabelRuns("∠", false)[0]!.family).toBe(MATH_FONT);
    expect(keyLabelRuns("ℝ", false)[0]).toMatchObject({ text: "R", family: MATH_SYMBOL_FONT });
    expect(keyLabelRuns("∴", false)[0]!.family).toBe(MATH_SYMBOL_FONT);
    expect(keyLabelRuns("∉", false)[0]).toMatchObject({ text: "∈", negated: true });
    expect(keyLabelRuns("x", true)[0]!.family).toBe(MATH_VARIABLE_FONT);
  });

  it("shrinks wider labels so the widest fits a 52pt key", () => {
    expect(keyLabelSize(keyLabelSegments("π"))).toBe(20);
    expect(keyLabelSize(keyLabelSegments("sin"))).toBe(17);
    expect(keyLabelSize(keyLabelSegments("cosh^{−1}"))).toBe(14);
  });

  it("keeps every label on one line and caps text scaling", async () => {
    const { getAllByText } = await render(
      <MathKey label="cosh^{−1}" testID="k" accessibilityLabel="Arccosh" onPress={() => undefined} height={44} />,
    );
    for (const node of [...getAllByText("cosh"), ...getAllByText("−1")]) {
      expect(node.props.numberOfLines).toBe(1);
      expect(node.props.maxFontSizeMultiplier).toBe(KEY_FONT_SCALE_MAX);
    }
  });

  it("draws a word label in the UI face's semibold, a symbol in its maths face", async () => {
    const { getByText } = await render(
      <MathKey label="sin" testID="k" accessibilityLabel="Sine" onPress={() => undefined} height={44} />,
    );
    expect(StyleSheet.flatten(getByText("sin").props.style)).toMatchObject({
      fontFamily: UI_FONT_FAMILY,
      fontWeight: "600",
    });
    const symbol = await render(
      <MathKey label="∠" testID="a" accessibilityLabel="Angle" onPress={() => undefined} height={44} />,
    );
    expect(StyleSheet.flatten(symbol.getByText("∠").props.style)).toMatchObject({
      fontFamily: MATH_FONT,
      fontWeight: "400",
    });
  });
});

import { Dimensions, Platform, StyleSheet } from "react-native";
import { render } from "@testing-library/react-native";

import { MathText } from "@/components/rich/MathText";
import { MATH_NOT_GLYPH, NEGATED_RELATION, NOT_ADVANCE_EM, notSlashSpacing } from "@/lib/math/glyphs";
import type { Element } from "./support/mathInk";

const SPACE_EM = 0.25;

/**
 * Where each glyph of [lead?][slash][base] is drawn and how far the pen goes, in em, as each
 * platform applies a Text's letterSpacing: iOS after the glyph, Android half before and half
 * after it (its text layout splits the spacing around every glyph).
 */
function drawn(android: boolean, baseEm: number): { slash: number; base: number; advance: number } {
  const spacing = notSlashSpacing(android);
  let pen = 0;
  const place = (advance: number, letterSpacing: number) => {
    const at = pen + (android ? letterSpacing / 2 : 0);
    pen += advance + letterSpacing;
    return at;
  };
  if (spacing.lead != null) place(SPACE_EM, spacing.lead);
  const slash = place(NOT_ADVANCE_EM, spacing.slash);
  const base = place(baseEm, 0);
  return { slash, base, advance: pen };
}

describe("negated relations", () => {
  beforeEach(() => {
    jest.spyOn(Dimensions, "get").mockReturnValue({ width: 390, height: 844, scale: 3, fontScale: 1 });
  });

  afterEach(() => {
    Platform.OS = "ios";
    jest.restoreAllMocks();
  });

  // The S23 drew ≠ as "/=", the slash on the end of the bar (2026-11-13): the pull that lays
  // it over the `=` on iOS moves it half an advance too far on Android.
  it.each([false, true])("lays the slash on its relation, the pair as wide as the relation (android=%s)", (android) => {
    for (const { widthEm } of Object.values(NEGATED_RELATION)) {
      const at = drawn(android, widthEm);
      expect(at.slash).toBeCloseTo(at.base, 6);
      expect(at.base).toBeCloseTo(0, 6);
      expect(at.advance).toBeCloseTo(widthEm, 6);
    }
  });

  it.each(["ios", "android"] as const)("draws ≠ with the spacing its platform needs (%s)", async (os) => {
    Platform.OS = os;
    const screen = await render(<MathText latex={String.raw`x \neq 9`} fontSize={16} />);
    const negated = screen.getByTestId("math-negated");
    expect(negated.props.accessibilityLabel).toBe("≠");
    const spacing = notSlashSpacing(os === "android");
    const pieces = negated.children.filter((child) => typeof child !== "string") as unknown as Element[];
    const slash = pieces.find((child) => (child.children ?? []).join("") === MATH_NOT_GLYPH)!;
    expect(StyleSheet.flatten(slash.props.style as object).letterSpacing).toBeCloseTo(spacing.slash * 16, 6);
    const lead = pieces.find((child) => (child.children ?? []).join("") === " ");
    if (spacing.lead == null) expect(lead).toBeUndefined();
    else expect(StyleSheet.flatten(lead!.props.style as object).letterSpacing).toBeCloseTo(spacing.lead * 16, 6);
    expect(negated).toHaveTextContent(new RegExp(`${MATH_NOT_GLYPH}=$`));
  });

  // iOS sets letterSpacing as written while the glyphs grow with Larger Text; Android grows
  // the letterSpacing with them, so it takes the unscaled pull.
  it.each([
    ["ios", 1.5, -NOT_ADVANCE_EM * 16 * 1.5],
    ["android", 1.5, -2 * NOT_ADVANCE_EM * 16],
  ] as const)("pulls the slash by the right amount at a larger text size (%s)", async (os, fontScale, pull) => {
    Platform.OS = os;
    jest.spyOn(Dimensions, "get").mockReturnValue({ width: 390, height: 844, scale: 3, fontScale });
    const screen = await render(<MathText latex={String.raw`x \neq 9`} fontSize={16} />);
    const pieces = screen.getByTestId("math-negated").children.filter((child) => typeof child !== "string") as unknown as Element[];
    const slash = pieces.find((child) => (child.children ?? []).join("") === MATH_NOT_GLYPH)!;
    expect(StyleSheet.flatten(slash.props.style as object).letterSpacing).toBeCloseTo(pull, 6);
  });
});

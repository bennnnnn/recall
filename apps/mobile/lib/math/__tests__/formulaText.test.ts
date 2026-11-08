/**
 * A formula on one line of symbols keeps its grouping: the bar and the raised exponent a
 * drawing shows become parentheses, so the line never reads as other maths.
 */
import { formulaText } from "@/lib/math/formulaText";

describe("formulaText", () => {
  it.each([
    [String.raw`a = \frac{v_f - v_i}{t}`, "a = (v_f - v_i)/t"],
    [String.raw`\frac{27-0}{9}`, "(27-0)/9"],
    [String.raw`\frac{1}{2a}`, "1/(2a)"],
    [String.raw`\frac{1}{2}mv^2`, "(1/2)mv^2"],
    [String.raw`x^{n+1}`, "x^(n+1)"],
    [String.raw`e^{-x^2}`, "e^(-x^2)"],
    [String.raw`x^\frac{1}{2}`, "x^(1/2)"],
    [String.raw`\sum_{i=1}^{n} i`, "Σ_(i=1)^n i"],
  ])("groups %s", (latex, shown) => {
    expect(formulaText(latex)).toBe(shown);
  });

  it("leaves a fraction of single terms and a short script bare", () => {
    expect(formulaText(String.raw`\frac{x^2}{4}`)).toBe("x^2/4");
    expect(formulaText(String.raw`\frac{\mathrm{m}}{\mathrm{s}^2}`)).toBe("m/s^2");
    expect(formulaText(String.raw`v_0 = 20\,\mathrm{m/s}`)).toBe("v_0 = 20 m/s");
    expect(formulaText(String.raw`t_{\text{flight}}`)).toBe("t_flight");
    expect(formulaText(String.raw`x^{-1}`)).toBe("x^-1");
    expect(formulaText(String.raw`30^\circ`)).toBe("30°");
  });
});

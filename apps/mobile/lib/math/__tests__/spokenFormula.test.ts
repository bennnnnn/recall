/**
 * A formula's words keep its grouping. Screen-reader labels read the symbol line, which
 * dropped it: (v_f − v_i)/t was read "v_f - v_i/t" and (27 − 0)/9 "27 - 0/9".
 */
import { spokenFormula } from "@/lib/math/spokenFormula";

describe("spokenFormula", () => {
  it.each([
    [String.raw`a = \frac{v_f - v_i}{t}`, "a = v subscript f - v subscript i, all over t"],
    [String.raw`\frac{27-0}{9}`, "27-0, all over 9"],
    [String.raw`\frac{1}{x+1}`, "1 over the quantity x+1"],
    [String.raw`\frac{a+b}{c-d} + 1`, "a+b, all over the quantity c-d, + 1"],
    [String.raw`x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}`, "x = -b plus or minus the square root of b squared - 4ac, all over 2a"],
    [String.raw`\frac{\sqrt{2}}{2}`, "the square root of 2, all over 2"],
    [String.raw`\frac{1}{2}mv^2`, "1 over 2, mv squared"],
  ])("says the grouping of %s", (latex, spoken) => {
    expect(spokenFormula(latex)).toBe(spoken);
  });

  it("ends a sum under a root or in a power on a pause", () => {
    expect(spokenFormula(String.raw`\sqrt{x+1} + 2`)).toBe("the square root of x+1, + 2");
    expect(spokenFormula(String.raw`x^{n+1} - 1`)).toBe("x to the power of n+1, - 1");
    expect(spokenFormula(String.raw`a_{n+1}`)).toBe("a subscript n+1");
  });

  // "2\frac{1}{2}" was "21 over 2", "20{,}000\frac{0.005}{12}" "20,0000.005 over 12".
  it("reads a number written onto a fraction or a root as its own term", () => {
    expect(spokenFormula(String.raw`2\frac{1}{2}`)).toBe("2 and 1 half");
    expect(spokenFormula(String.raw`1\frac{3}{4}`)).toBe("1 and 3 quarters");
    expect(spokenFormula(String.raw`5\frac{1}{12}`)).toBe("5 and 1 over 12");
    expect(spokenFormula(String.raw`20{,}000\frac{0.005}{12}`)).toBe("20,000 times 0.005 over 12");
    expect(spokenFormula(String.raw`2\frac{x}{3}`)).toBe("2 times x over 3");
    expect(spokenFormula(String.raw`2\sqrt{3}`)).toBe("2 times the square root of 3");
  });

  // "(1+r)^n-1" was "to the power of n-1", heard as one exponent.
  it("closes a power before the next term", () => {
    expect(spokenFormula(String.raw`(1+r)^n-1`)).toBe("(1+r) to the power of n, -1");
    expect(spokenFormula(String.raw`(1.005)^{60} - 1`)).toBe("(1.005) to the power of 60, - 1");
    expect(spokenFormula(String.raw`v_0 = 20`)).toBe("v subscript 0 = 20");
    expect(spokenFormula(String.raw`x^2 - 1`)).toBe("x squared - 1");
    expect(spokenFormula(String.raw`\mathrm{H_2O}`)).toBe("H subscript 2 O");
  });

  it("keeps a simple fraction, a sign and a power as they were said", () => {
    expect(spokenFormula(String.raw`\frac{\Delta v}{\Delta t}`)).toBe("Δ v over Δ t");
    expect(spokenFormula(String.raw`\frac{-1}{2}`)).toBe("-1 over 2");
    expect(spokenFormula(String.raw`v_0 = 20\,\mathrm{m/s}`)).toBe("v subscript 0 = 20 m/s");
    expect(spokenFormula(String.raw`30^\circ`)).toBe("30 degrees");
    expect(spokenFormula(String.raw`\left(\frac{a+b}{2}\right)^2`)).toBe("(a+b, all over 2) squared");
  });
});

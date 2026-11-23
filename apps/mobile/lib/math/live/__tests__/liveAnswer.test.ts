import { liveAnswer } from "@/lib/math/live/answer";

const answer = (draft: string) => liveAnswer(draft, "undefined");
const shown = (draft: string) => answer(draft)?.latex ?? null;

describe("liveAnswer", () => {
  it("updates as each key lands", () => {
    expect(shown("$3$")).toBeNull();
    expect(shown("$3+$")).toBeNull();
    expect(shown("$3+1$")).toBe("= 4");
    expect(shown("$3+1\\times $")).toBeNull();
    expect(shown("$3+1\\times 2$")).toBe("= 5");
    expect(shown("$3+1\\times 2+2$")).toBe("= 7");
  });

  it.each([
    ["3+1*2", "= 5"],
    ["$0.1+0.2$", "= 0.3"],
    ["$7\\div 4$", "= 1.75"],
    ["$1\\div 3$", "= \\frac{1}{3} \\approx 0.3333333333"],
    ["$\\frac{1}{2}+\\frac{1}{4}$", "= \\frac{3}{4} = 0.75"],
    ["$\\frac{1}{2}+\\frac{1}{3}$", "= \\frac{5}{6} \\approx 0.8333333333"],
    ["$\\frac{3}{4}$", "= 0.75"],
    ["$\\frac{6}{4}$", "= \\frac{3}{2} = 1.5"],
    ["$-3^{2}$", "= -9"],
    ["$\\sqrt{2}$", "\\approx 1.414213562"],
    ["$\\sin(30^{\\circ})$", "= 0.5"],
    ["$\\pi $", "\\approx 3.141592654"],
    ["$2^{100}$", "\\approx 1.2676506 \\times 10^{30}"],
    ["$0.000001\\times 3$", "= 0.000003"],
    ["$10^{-7}$", "= 0.0000001"],
    ["$123456789012\\times 10$", "= 1234567890120"],
  ])("%s shows %s", (draft, latex) => {
    expect(shown(draft)).toBe(latex);
  });

  it("works a draft out when = is pressed at its end, as a calculator does", () => {
    expect(shown("$3+4=$")).toBe("= 7");
    expect(shown("$3\\times (2+1) = $")).toBe("= 9");
    expect(shown("$\\frac{1}{3}=$")).toBe("\\approx 0.3333333333");
    // An equation, a lone number or a letter before = is no calculation.
    expect(shown("$2+2=4$")).toBeNull();
    expect(shown("$3=$")).toBeNull();
    expect(shown("$x+1=$")).toBeNull();
  });

  it("says when the value shown is rounded", () => {
    expect(answer("$\\sqrt{2}$")).toMatchObject({ exact: false, spoken: "≈ 1.414213562" });
    expect(answer("$2+3$")).toMatchObject({ exact: true, spoken: "5" });
  });

  it.each([
    ["an open box", "$\\sqrt{}$"],
    ["a closing point", "$3.$"],
    ["a variable", "$2x$"],
    ["Greek", "$\\theta +1$"],
    ["prose", "add $2+3$ please"],
    ["two spans", "$2$ and $3$"],
    ["no digits", "e"],
    ["spaced digits", "$2 3$"],
    ["a set", "$\\{1,2\\}$"],
    ["infinity", "$\\infty +1$"],
    ["a product sign", "$\\prod_{k=1}^{5}k$"],
    ["a derivative", "$\\frac{d}{dx}(x^{3})$"],
    ["a huge factorial", "$1000!$"],
    ["a fractional factorial", "$2.5!$"],
  ])("shows nothing for %s", (_label, draft) => {
    expect(answer(draft)).toBeNull();
  });

  it.each([
    ["a zero divisor", "$1\\div 0$"],
    ["zero over zero", "$0\\div 0$"],
    ["a fraction over zero", "$\\frac{1}{2-2}$"],
    ["a remainder by zero", "$5\\bmod 0$"],
    ["zero to a negative power", "$0^{-1}$"],
    ["a tangent pole", "$\\tan(90^{\\circ})$"],
    ["a tangent pole in radians", "$\\tan(\\frac{\\pi}{2})$"],
    ["a cotangent pole", "$\\cot(180^{\\circ})$"],
    ["a hyperbolic pole", "$\\coth(0)$"],
    ["a log of zero", "$\\log(0)$"],
    ["a natural log of zero", "$\\ln(0)$"],
    ["a log to base 1", "$\\log_{1}(5)$"],
    ["a divisor that works out to zero", "$\\frac{3}{\\sin(180^{\\circ})}$"],
  ])("says undefined for %s", (_label, draft) => {
    expect(answer(draft)).toEqual({
      latex: "= \\text{undefined}",
      lines: ["= \\text{undefined}"],
      spoken: "undefined",
      exact: true,
    });
  });

  it("says undefined in the app's language", () => {
    expect(liveAnswer("$1\\div 0$", "indéfini")?.latex).toBe("= \\text{indéfini}");
    expect(liveAnswer("$1\\div 0$", "не определено")?.latex).toBe("= \\text{не определено}");
  });

  it("keeps 0^0 at 1, as the server reads it", () => {
    expect(shown("$0^{0}$")).toBe("= 1");
  });

  it.each([
    ["a root of a negative", "$\\sqrt{-4}$"],
    ["a log of a negative", "$\\log(-1)$"],
    ["a branch that is not real", "$\\sqrt{1\\pm 2}$"],
    ["a sign with nothing to work out", "$\\pm 3$"],
    ["more than four values", "$1\\pm 2\\pm 4\\pm 8$"],
    ["a fourth sign", "$1\\pm 0\\pm 0\\pm 0\\pm 0$"],
    ["two signs with an undefined branch", "$\\frac{1}{2\\pm 1\\pm 1}$"],
    ["a thousands comma", "$1,000$"],
    ["a sum with a thousands comma", "$1,000+1$"],
    ["a typed thousands comma", "1,000+1"],
    ["a braced thousands comma", "$1{,}000\\times 2$"],
    ["a thin space between digits", "$1\\,000+1$"],
    ["a decimal comma", "$2,5+1$"],
  ])("shows nothing for %s", (_label, draft) => {
    expect(answer(draft)).toBeNull();
  });

  it.each([
    ["$2\\pm 1$", ["2- 1 = 1", "2+ 1 = 3"]],
    ["$2\\mp 1$", ["2- 1 = 1", "2+ 1 = 3"]],
    ["2±1", ["2-1 = 1", "2+1 = 3"]],
    ["3*2∓1", ["3\\times 2-1 = 5", "3\\times 2+1 = 7"]],
    ["$10\\pm 2\\times 3$", ["10- 2\\times 3 = 4", "10+ 2\\times 3 = 16"]],
    ["$(2\\pm 1)^{2}$", ["(2- 1)^{2} = 1", "(2+ 1)^{2} = 9"]],
    ["$1\\pm\\sqrt{2}$", ["1-\\sqrt{2} \\approx -0.4142135624", "1+\\sqrt{2} \\approx 2.414213562"]],
    ["$5\\times\\pm 2$", ["5\\times- 2 = -10", "5\\times+ 2 = 10"]],
  ])("writes out both branches of %s, the minus first", (draft, lines) => {
    expect(answer(draft)?.lines).toEqual(lines);
    expect(shown(draft)).toBe(lines.join(",\\quad "));
  });

  it("writes stacked branches side by side, each value once", () => {
    expect(answer("$\\frac{-3\\pm\\sqrt{9-8}}{2}$")?.lines).toEqual([
      "\\frac{-3-\\sqrt{9-8}}{2} = -2,\\quad \\frac{-3+\\sqrt{9-8}}{2} = -1",
    ]);
    expect(answer("$\\frac{1}{1\\pm 1}$")?.lines).toEqual([
      "\\frac{1}{1- 1} = \\text{undefined},\\quad \\frac{1}{1+ 1} = 0.5",
    ]);
    expect(answer("$\\frac{1}{3}\\pm 1$")?.lines).toEqual([
      "\\frac{1}{3}- 1 = -\\frac{2}{3},\\quad \\frac{1}{3}+ 1 = \\frac{4}{3}",
    ]);
  });

  it("works = out on a ± draft too", () => {
    expect(answer("$2\\pm 1=$")?.lines).toEqual(["2- 1 = 1", "2+ 1 = 3"]);
  });

  it("speaks a ± draft's values", () => {
    expect(answer("$2\\pm 1$")).toMatchObject({ spoken: "1, 3", exact: true });
    expect(answer("$1\\pm\\sqrt{2}$")).toMatchObject({ exact: false });
  });

  it.each([
    ["$1\\pm 1\\pm 1$", "= -1,\\quad 1,\\quad 3"],
    ["$1\\pm 2\\mp 4$", "= -5,\\quad -1,\\quad 3,\\quad 7"],
    ["$1\\pm 0\\pm 0$", "= 1"],
    ["$\\pm 1\\pm 1$", "= -2,\\quad 0,\\quad 2"],
    ["$\\sqrt{2}\\pm 1\\pm 1$", "\\approx -0.5857864376,\\quad \\approx 1.414213562,\\quad \\approx 3.414213562"],
  ])("shows each distinct value of %s, smallest first", (draft, latex) => {
    expect(shown(draft)).toBe(latex);
  });

  it("reads the keys' spacing and sized brackets", () => {
    expect(shown("$\\left(2+3\\right)\\times 4$")).toBe("= 20");
    expect(shown("$2\\,+\\,3$")).toBe("= 5");
  });
});

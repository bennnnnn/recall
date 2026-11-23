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
    // A typed fraction, negative or not, is shown by its decimal: only that is new.
    ["$-\\frac{3}{4}$", "= -0.75"],
    ["$-\\frac{1}{3}$", "\\approx -0.3333333333"],
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
    ["an undefined term in a sum", "$2+1\\div 0$"],
    ["an undefined factor", "$3\\times\\frac{1}{0}$"],
    ["an undefined numerator", "$\\frac{\\tan(90^{\\circ})}{2}$"],
    ["a pole far round the circle", "$\\tan(1890^{\\circ})$"],
    ["a pole many turns round", "$\\tan(9000090^{\\circ})$"],
    ["a sine zero many turns round", "$\\frac{1}{\\sin(9000000^{\\circ})}$"],
  ])("says undefined for %s", (_label, draft) => {
    expect(answer(draft)).toEqual({ latex: "= \\text{undefined}", signed: false, spoken: "undefined", exact: true });
  });

  it("says undefined in the app's language, as plain letters", () => {
    // A sign with a meaning in LaTeX is dropped: `a_b{c}` would draw b as a subscript.
    expect(liveAnswer("$1\\div 0$", "a_b{c}")?.latex).toBe("= \\text{abc}");
    expect(liveAnswer("$1\\div 0$", "indéfini")?.latex).toBe("= \\text{indéfini}");
    expect(liveAnswer("$1\\div 0$", "не определено")?.latex).toBe("= \\text{не определено}");
  });

  it("keeps 0^0 at 1, as the server reads it", () => {
    expect(shown("$0^{0}$")).toBe("= 1");
  });

  it.each([
    ["a root of a negative", "$\\sqrt{-4}$"],
    ["a log of a negative", "$\\log(-1)$"],
    ["an infinity, which the server does not call undefined", "$\\tanh^{-1}(1)$"],
    ["a divisor that rounded to 0", "$\\frac{1}{10^{-400}}$"],
    ["a log of a number that rounded to 0", "$\\ln(e^{-1000})$"],
    ["± and ∓ together", "$1\\pm 2\\mp 4$"],
    ["a sign after a minus with nothing to work out", "$-\\pm 3$"],
    ["an undefined divisor, which SymPy calls 0", "$1\\div\\tan(90^{\\circ})$"],
    ["a log of zero as a divisor", "$1\\div\\ln(0)$"],
    ["an undefined inside |x|, which SymPy calls infinite", "$\\left|1\\div 0\\right|$"],
    ["an undefined to the power 0, which SymPy calls 1", "$(1\\div 0)^{0}$"],
    ["a cosine that is only small, not a pole", "$\\tan(89.99999999999)$"],
    ["a cosine within rounding of 0, not a pole", "$\\tan(89.99999999999999)$"],
    ["a sine that is only small, not a pole", "$\\csc(0.00000000001)$"],
    ["a sine near 0, not a pole", "$\\csc(0.00000000000001)$"],
    ["a log base that only rounds to 1", "$\\log_{1.0000000000000001}(5)$"],
    ["a negative percent in a sum", "$2\\pm -3\\%$"],
    ["a radian angle too big to keep ten digits", "$\\cos(10^{15}\\pi+1)$"],
    ["an angle in π only near a pole", "$\\tan(\\frac{\\pi}{2}+10^{-15})$"],
    ["an angle in π that rounded to 0", "$\\csc(10^{-400}\\pi)$"],
    ["a radian angle only near a pole", "$\\tan(1.5707963267948966\\mathrm{rad})$"],
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
    ["$2\\pm 1$", ["2 - 1 = 1", "2 + 1 = 3"]],
    ["$2\\mp 1$", ["2 - 1 = 1", "2 + 1 = 3"]],
    ["2±1", ["2 - 1 = 1", "2 + 1 = 3"]],
    ["3*2∓1", ["3 \\times 2 - 1 = 5", "3 \\times 2 + 1 = 7"]],
    ["$10\\pm 2\\times 3$", ["10 - 2 \\times 3 = 4", "10 + 2 \\times 3 = 16"]],
    ["$(2\\pm 1)^{2}$", ["(2 - 1)^{2} = 1", "(2 + 1)^{2} = 9"]],
    ["$1\\pm\\sqrt{2}$", ["1 - \\sqrt{2} \\approx -0.4142135624", "1 + \\sqrt{2} \\approx 2.414213562"]],
    ["$5\\times\\pm 2$", ["5 \\times -2 = -10", "5 \\times +2 = 10"]],
  ])("writes out both branches of %s side by side, the minus first", (draft, branches) => {
    expect(shown(draft)).toBe(branches.join(",\\quad "));
  });

  it("writes each branch's value once", () => {
    expect(shown("$\\frac{-3\\pm\\sqrt{9-8}}{2}$")).toBe(
      "\\frac{-3 - \\sqrt{9 - 8}}{2} = -2,\\quad \\frac{-3 + \\sqrt{9 - 8}}{2} = -1",
    );
    expect(shown("$\\frac{1}{1\\pm 1}$")).toBe(
      "\\frac{1}{1 - 1} = \\text{undefined},\\quad \\frac{1}{1 + 1} = \\frac{1}{2}",
    );
    expect(shown("$\\frac{1}{3}\\pm 1$")).toBe(
      "\\frac{1}{3} - 1 = -\\frac{2}{3},\\quad \\frac{1}{3} + 1 = \\frac{4}{3}",
    );
  });

  it("writes all of a draft's values in one form", () => {
    // A value that needs a fraction makes every value one, with no fraction typed.
    expect(shown("$1\\div 3\\pm 1\\div 6$")).toBe(
      "1 \\div 3 - 1 \\div 6 = \\frac{1}{6},\\quad 1 \\div 3 + 1 \\div 6 = \\frac{1}{2}",
    );
    // A typed fraction does too.
    expect(shown("$\\frac{1}{3}\\pm\\frac{1}{6}$")).toBe(
      "\\frac{1}{3} - \\frac{1}{6} = \\frac{1}{6},\\quad \\frac{1}{3} + \\frac{1}{6} = \\frac{1}{2}",
    );
    // No fraction typed or needed: decimals.
    expect(shown("$2.5\\pm 0.25$")).toBe("2.5 - 0.25 = 2.25,\\quad 2.5 + 0.25 = 2.75");
  });

  it("gives a branch that is its own fraction its decimal, the sign inside or out", () => {
    expect(shown("$\\frac{\\pm 1}{2}$")).toBe("\\frac{-1}{2} = -0.5,\\quad \\frac{+1}{2} = 0.5");
    expect(shown("$\\frac{1}{\\pm 3}$")).toMatch(/\\approx -0\.3333333333,.*\\approx 0\.3333333333$/);
    // Two minus signs cancel: the + branch of -±1/3 is its own fraction too.
    expect(answer("$-\\pm\\frac{1}{3}$")?.latex).toMatch(/^\+ ?\\frac\{1\}\{3\} \\approx 0\.3333333333,/);
    expect(shown("$\\pm\\frac{1}{3}$")).toBe(
      "-\\frac{1}{3} \\approx -0.3333333333,\\quad +\\frac{1}{3} \\approx 0.3333333333",
    );
  });

  it("writes once the values the display rounds alike", () => {
    expect(shown("$10^{20}\\pm 1\\pm 1$")).toBe("\\approx 1 \\times 10^{20}");
    // Eight values, one as written: the cap counts what the display writes.
    expect(shown("$10^{20}\\pm 1\\pm 2\\pm 4$")).toBe("\\approx 1 \\times 10^{20}");
    expect(shown("$1\\pm 10^{-12}\\pm 10^{-12}$")).toBe("\\approx 1");
  });

  it("keeps values apart that differ in the tenth digit", () => {
    expect(shown("$\\pi\\pm 10^{-9}\\pm 10^{-9}$")?.split(",").length).toBe(3);
  });

  it("keeps values apart that differ in the digits shown, however small", () => {
    expect(answer("$\\sqrt{2}\\times 10^{-5}\\pm 10^{-10}\\pm 10^{-10}$")?.latex.split(",").length).toBe(3);
  });

  it("merges a sign typed beside + or − instead of doubling it", () => {
    expect(shown("$2\\pm -3$")).toBe("2 + 3 = 5,\\quad 2 - 3 = -1");
    expect(shown("$2-\\pm 3$")).toBe("2 + 3 = 5,\\quad 2 - 3 = -1");
    expect(shown("$2--\\pm 3$")).toBe("2 - 3 = -1,\\quad 2 + 3 = 5");
    expect(shown("$2+\\pm 3$")).toBe("2 - 3 = -1,\\quad 2 + 3 = 5");
    expect(shown("$2\\times\\pm 3$")).toBe("2 \\times -3 = -6,\\quad 2 \\times +3 = 6");
  });

  it("shows the values alone where merging signs beside a mod would write a false line", () => {
    // 5 - ((-2) mod 3) is 4, but "5 + 2 mod 3" reads as 7. Still the − branch first.
    expect(shown("$5-\\pm 2\\bmod 3$")).toBe("= 4,\\quad 3");
    expect(shown("$5\\bmod(2-\\pm 2)$")).toBe("= 1,\\quad \\text{undefined}");
  });

  it("works large angles away from any pole", () => {
    expect(shown("$\\cos(400\\pi)$")).toBe("= 1");
    // An exact multiple of π is worked as exact degrees, however large or cancelled.
    expect(shown("$\\cos(10^{15}\\pi)$")).toBe("= 1");
    expect(shown("$\\sin(\\pi-\\pi)$")).toBe("= 0");
    expect(shown("$\\cos(2\\pi-2\\pi)$")).toBe("= 1");
    // A step whole numbers fool is no multiple of π: floor π is 3.
    expect(shown("$\\sin(\\lfloor\\pi\\rfloor)$")).toBe("\\approx 0.1411200081");
    expect(shown("$\\tan(\\lfloor\\frac{\\pi}{2}\\rfloor)$")).toBe("\\approx 1.557407725");
    expect(shown("$\\sin(400\\pi+\\frac{\\pi}{6})$")).toMatch(/^(=|\\approx) 0\.5$/);
    // Exact degrees are taken within one turn first: 36000000000000030° is 30°.
    expect(shown("$\\sin(36000000000000030^{\\circ})$")).toBe("= 0.5");
  });

  it("works an angle of 0π out exactly", () => {
    expect(shown("$\\cos(0\\pi)$")).toBe("= 1");
  });

  it("works nested degree angles once each, not twice per level", () => {
    let draft = "1";
    for (let i = 0; i < 24; i += 1) draft = "\\sin(" + draft + "^{\\circ})";
    const started = Date.now();
    expect(shown("$" + draft + "$")).not.toBeNull();
    expect(Date.now() - started).toBeLessThan(1000);
  });

  it("works = out on a ± draft too", () => {
    expect(shown("$2\\pm 1=$")).toBe("2 - 1 = 1,\\quad 2 + 1 = 3");
  });

  it("speaks a ± draft's values, and draws them at the draft's size", () => {
    // Each branch read out, so a listener knows which value is which.
    expect(answer("$2\\pm 1$")).toMatchObject({ spoken: "2 - 1 = 1, 2 + 1 = 3", exact: true, signed: true, short: "= 1,\\quad 3" });
    expect(answer("$\\frac{1}{1\\pm 1}$")?.short).toBe("= \\text{undefined},\\quad \\frac{1}{2}");
    expect(answer("$1\\pm 1\\pm 1$")).toMatchObject({ signed: true });
    expect(answer("$2+1$")).toMatchObject({ signed: false });
    expect(answer("$1\\pm\\sqrt{2}$")).toMatchObject({ exact: false });
  });

  it.each([
    ["$1\\pm 1\\pm 1$", "= -1,\\quad 1,\\quad 3"],
    ["$1\\mp 2\\mp 4$", "= -5,\\quad -1,\\quad 3,\\quad 7"],
    ["$1\\pm 4\\pm 2$", "= -5,\\quad -1,\\quad 3,\\quad 7"],
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

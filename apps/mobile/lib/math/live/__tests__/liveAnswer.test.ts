import { liveAnswer } from "@/lib/math/live/answer";

const shown = (draft: string) => liveAnswer(draft)?.latex ?? null;

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

  it("says when the value shown is rounded", () => {
    expect(liveAnswer("$\\sqrt{2}$")).toMatchObject({ exact: false, spoken: "≈ 1.414213562" });
    expect(liveAnswer("$2+3$")).toMatchObject({ exact: true, spoken: "5" });
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
    expect(liveAnswer(draft)).toBeNull();
  });

  it("reads the keys' spacing and sized brackets", () => {
    expect(shown("$\\left(2+3\\right)\\times 4$")).toBe("= 20");
    expect(shown("$2\\,+\\,3$")).toBe("= 5");
  });
});

import { uprightNotation } from "@/lib/math/latexUpright";

describe("uprightNotation", () => {
  it.each([
    // Live, 2026-11-02: a model's chemistry maths drew units, words and formulas italic.
    ["M = 58.44g/mol", String.raw`M = 58.44\,\mathrm{g/mol}`],
    ["2H₂ : 2H₂O, so 1:1", String.raw`2\mathrm{H₂} : 2\mathrm{H₂O},\text{ so }1:1`],
    ["n(H₂O) = 2.0 mol", String.raw`n(\mathrm{H₂O}) = 2.0\,\mathrm{mol}`],
    ["[Fe³⁺] = 0.1 M", String.raw`[\mathrm{Fe³⁺}] = 0.1\,\mathrm{M}`],
    [String.raw`N = 6.022 \times 10^{23} mol^{-1}`, String.raw`N = 6.022 \times 10^{23}\,\mathrm{mol}^{-1}`],
    ["v = 20 m/s", String.raw`v = 20\,\mathrm{m/s}`],
    ["t = 5 s", String.raw`t = 5\,\mathrm{s}`],
    ["T = 25 °C", String.raw`T = 25\,^\circ\mathrm{C}`],
    ["A = 4 m^2", String.raw`A = 4\,\mathrm{m}^{2}`],
    ["E = 12 kJ per mol", String.raw`E = 12\,\mathrm{kJ}\text{ per }mol`],
  ])("%s", (source, upright) => {
    expect(uprightNotation(source)).toBe(upright);
  });

  it.each([
    // Algebra, symbols and what is upright already stay as written.
    "v = u + at",
    "2x + 5m = 3",
    "C₁V₁ = C₂V₂",
    "V₂ = 2.0",
    "y = 3 g(x)",
    String.raw`v = 20\,\mathrm{m/s}`,
    String.raw`5\text{ m}`,
    String.raw`\frac{1}{2} m v^2`,
    "x_{2} + y^{10}",
    "f(x) = x^2",
    // A number times a variable whose letter is also a unit's.
    "E = 0.5 m v^2",
    "1/2 m v^2",
    "h = 0.5 g t^2",
    "F = 2 m a",
    "W = 3 N d",
    "3 A + 2 A",
    "2min(a,b)",
  ])("leaves %s alone", (source) => {
    expect(uprightNotation(source)).toBe(source);
  });

  // A grade 12 run (2026-11-13): words a reply wrote into its maths read as products of
  // italic letters, "extrema" as e·x·t·r·e·m·a.
  it.each([
    ["extrema", String.raw`\mathrm{extrema}`],
    [String.raw`increasing = (-\infty,-3) \cup (1,\infty)`, String.raw`\mathrm{increasing} = (-\infty,-3) \cup (1,\infty)`],
    ["Area = 24", String.raw`\mathrm{Area} = 24`],
    ["total cost = 5", String.raw`\mathrm{total}\ \mathrm{cost} = 5`],
    ["white_{pigment} = 3", String.raw`\mathrm{white}_{pigment} = 3`],
    [String.raw`\frac{1}{2} speed`, String.raw`\frac{1}{2} \mathrm{speed}`],
  ])("sets the word in %s upright", (source, upright) => {
    expect(uprightNotation(source)).toBe(upright);
  });

  it.each([
    // Products of variables, vertices, a variable's run with no vowel, and a command's own word.
    "mgh = 10", "abc + xyz", "F = ma", "ABCD", "PQRS", "dxdy", "nRT",
    String.raw`\begin{aligned} x &= 1 \end{aligned}`,
    String.raw`\mathbf{vector}`,
    String.raw`\color{green} x`,
    String.raw`\sin x + \lim_{x \to 0} f`,
  ])("keeps %s as maths", (source) => {
    expect(uprightNotation(source)).toBe(source);
  });

  it.each([
    ["α = 1.2×10⁻⁵ K⁻¹", "K⁻¹"],
    ["β = 3×10⁻⁴ °C⁻¹", "C⁻¹"],
    ["k = 0.5 s⁻¹", "s⁻¹"],
    ["E = 2 V⁻¹", "V⁻¹"],
  ])("reads the ⁻ in %s as an exponent, not an ion's charge", (source, unit) => {
    const out = uprightNotation(source);
    expect(out).not.toMatch(/\\mathrm\{[A-Z][a-z]?⁻\}/);
    expect(out).toContain(unit);
  });

  it.each([
    ["[SO₄²⁻] = 0.2 M", "\\mathrm{SO₄²⁻}"],
    ["K⁺ and Cl⁻ ions", "\\mathrm{K⁺}"],
  ])("still reads a charge in %s", (source, ion) => {
    expect(uprightNotation(source)).toContain(ion);
  });
});

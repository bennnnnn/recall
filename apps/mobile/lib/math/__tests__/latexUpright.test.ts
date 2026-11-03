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
  ])("leaves %s alone", (source) => {
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

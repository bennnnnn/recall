import { typedScriptsAsMath } from "@/lib/math/typedScripts";

describe("typedScriptsAsMath", () => {
  // A grade 12 student's questions (2026-11-13) showed their braces and carets as typed.
  it.each([
    ["Evaluate ∑_{k=1}^{10} (3k − 1)", "Evaluate $∑_{k=1}^{10}$ (3k − 1)"],
    ["Evaluate lim_{x→9} f(x)", "Evaluate $lim_{x→9}$ f(x)"],
    ["Find lim_{x→5⁺} f(x) and lim_{x→5⁻} f(x).", "Find $lim_{x→5⁺}$ f(x) and $lim_{x→5⁻}$ f(x)."],
    ["Find ∫_0^1 x dx", "Find $∫_0^1$ x dx"],
    ["the max_{x∈[0,1]} of f", "the $max_{x∈[0,1]}$ of f"],
    ["solve e^{2x} = 5", "solve $e^{2x}$ = 5"],
    ["Π_{i=1}^{n} a_i", "$Π_{i=1}^{n}$ a_i"],
  ])("reads %s", (typed, read) => {
    expect(typedScriptsAsMath(typed)).toBe(read);
    expect(typedScriptsAsMath(typed, { plain: false })).toBe(read);
  });

  it.each([
    ["Right-hand limit as x → 5^+", "Right-hand limit as x → $5^+$"],
    ["(left-hand limit as x → 5^-)", "(left-hand limit as x → $5^-$)"],
    ["E = mc^2", "E = $mc^2$"],
    ["10^-3 m", "$10^{-3}$ m"],
    ["x_1 + x_2", "$x_1$ + $x_2$"],
  ])("reads a bare power or index in %s, where words hold it", (typed, read) => {
    expect(typedScriptsAsMath(typed)).toBe(read);
    // A sent message leaves these to the markdown's implicit maths, brackets and all.
    expect(typedScriptsAsMath(typed, { plain: false })).toBe(typed);
  });

  it.each([
    [String.raw`(right-hand limit as x $\to 5$^+)`, String.raw`(right-hand limit as x $\to 5^+$)`],
    [String.raw`as x $\to 5$^-`, String.raw`as x $\to 5^-$`],
    ["$x$^{2} and $y$_1", "$x^{2}$ and $y_1$"],
  ])("joins a script glued after a formula to it: %s", (written, read) => {
    expect(typedScriptsAsMath(written)).toBe(read);
    expect(typedScriptsAsMath(written, { plain: false })).toBe(read);
  });

  it.each([
    "rename file_name to the C++ way",
    "an a_b test with snake_case_1 and var_{x}",
    "see https://example.com/a_{b}^2 and me@mail.com",
    "use `x^{2}` in code",
    "press Ctrl^C, not ^_^",
    "costs $5 and x^{2}",
    "already $x^{2}$ and done",
    "```\nlim_{x→0}\n```",
  ])("leaves %s as written", (text) => {
    expect(typedScriptsAsMath(text)).toBe(text);
  });
});

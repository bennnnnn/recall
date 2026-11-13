import { sentScriptsAsMath, typedScriptsAsMath } from "@/lib/math/typedScripts";

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
    ["∑_{k = 1}^{n} k", "$∑_{k = 1}^{n}$ k"],
  ])("reads %s", (typed, read) => {
    expect(typedScriptsAsMath(typed)).toBe(read);
    expect(typedScriptsAsMath(typed, { plain: false })).toBe(read);
  });

  // A word of maths is one span, never a piece of it: "x^{2}$y^{3}$" showed a dollar.
  it.each([
    ["Simplify x^{2}y^{3}", "Simplify $x^{2}y^{3}$"],
    ["Differentiate x^{3}e^{2x}", "Differentiate $x^{3}e^{2x}$"],
    ["Factor 6x^{2}y^{3} - 9xy", "Factor $6x^{2}y^{3}$ - 9xy"],
    ["Integrate x^{2}sin(x) dx", "Integrate $x^{2}sin(x)$ dx"],
    ["what is (x^{2}+1)^{3}?", "what is $(x^{2}+1)^{3}$?"],
    ["the inverse f^{-1}(x).", "the inverse $f^{-1}(x)$."],
  ])("reads the whole word in %s", (typed, read) => {
    expect(typedScriptsAsMath(typed)).toBe(read);
  });

  it.each([
    ["Right-hand limit as x → 5^+", "Right-hand limit as x → $5^+$"],
    ["(left-hand limit as x → 5^-)", "(left-hand limit as x → $5^-$)"],
    ["E = mc^2", "E = $mc^2$"],
    ["10^-3 m", "$10^-3$ m"],
    // A longer word's caret is no power, and the line's own power is still read.
    ["press Ctrl^C and x^2", "press Ctrl^C and $x^2$"],
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
    "see https://example.com/a_{b}^2, example.com/a_{1} and me@mail.com",
    "use `x^{2}` in code",
    "press Ctrl^C, not ^_^",
    "costs $5 and x^{2}",
    "already $x^{2}$ and done",
    "```\nlim_{x→0}\n```",
    // TeX of its own: the markdown reads it, delimiters, commands and all (review, 2026-11-13).
    String.raw`Solve \(x^{2} - 4 = 0\)`,
    String.raw`If \(a_{n} = 2n\), find \(a_{5}\).`,
    String.raw`\(x^{2}\)`,
    String.raw`\[x^{2}\]`,
    "$$x^{2}$$ and y^{3}",
    String.raw`\frac{x^{2}}{2}`,
    String.raw`\frac{1}{x^{2}}`,
    String.raw`Solve \frac{x^{2}}{4} = 1`,
    String.raw`\sqrt{x^{2}+1}`,
    "sqrt(x^{2}+1)",
    String.raw`Find \(\int_0^1 x^{2}\,dx\)`,
    // Code, links, images and emphasis are never cut through.
    "Why does `$x$^2` not work?",
    "`echo $A$_b`",
    "**x^{2}**",
    "**Bold** x_{i} *it*",
    "![img](a_{1}.png)",
    "[see](https://ex.com/x_{1})",
    // A glued script never meets the next formula's dollar.
    "$a$_{b}$c$",
    // A script in no word of maths leaves its line whole, never read in part.
    "(x^{2} - 4)/(x^{2} - x - 2)",
    "see example.com/a_{1} and lim_{x→0}",
  ])("leaves %s as written", (text) => {
    expect(typedScriptsAsMath(text)).toBe(text);
    expect(typedScriptsAsMath(text, { plain: false })).toBe(text);
  });
});

describe("sentScriptsAsMath", () => {
  // Lines the markdown's implicit maths already draws stay exactly as sent.
  it.each([
    "T_{n} = 2n + 1",
    "a_{n+1} = 2a_n",
    "f^{-1}(x)",
    "x^{2}+y^{2}=r^{2}",
    "2^{x} = 8",
    "Simplify (x^{2} - 4)/(x^{2} - x - 2).",
    String.raw`Solve \(x^{2} - 4 = 0\)`,
    String.raw`\frac{x^{2}}{2}`,
  ])("leaves %s to the implicit maths", (text) => {
    expect(sentScriptsAsMath(text)).toBe(text);
  });

  it.each([
    ["Evaluate ∑_{k=1}^{10} (3k − 1)", "Evaluate $∑_{k=1}^{10}$ (3k − 1)"],
    ["Find lim_{x→5⁺} f(x)", "Find $lim_{x→5⁺}$ f(x)"],
    ["what is 2^{10}?", "what is $2^{10}$?"],
    ["Simplify x^{2}y^{3}", "Simplify $x^{2}y^{3}$"],
  ])("reads %s where the implicit maths leaves its scripts", (typed, read) => {
    expect(sentScriptsAsMath(typed)).toBe(read);
  });
});

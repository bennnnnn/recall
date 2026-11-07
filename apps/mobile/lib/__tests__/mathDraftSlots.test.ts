import { findDraftNodes } from "@/lib/math/draftNodes";
import { caretAfterExpression, spliceMathBackspace } from "@/lib/math/draftSlots";
import { MATH_KEYBOARD_SYMBOLS, spliceMathInsert } from "@/lib/math/keyboardSymbols";

/** A draft with its caret marked `‸`, and back. */
const mark = ({ text, selection }: { text: string; selection: { start: number } }) =>
  `${text.slice(0, selection.start)}‸${text.slice(selection.start)}`;
const unmark = (marked: string) => {
  const caret = marked.indexOf("‸");
  return { text: marked.replace("‸", ""), selection: { start: caret, end: caret } };
};

/** The draft and its caret after each backspace from `‸`, until it empties or after `presses`. */
function backspaces(marked: string, presses = 12): string[] {
  let state = unmark(marked);
  const drafts: string[] = [];
  while (state.text && drafts.length < presses) {
    state = spliceMathBackspace(state.text, state.selection);
    drafts.push(mark(state));
  }
  return drafts;
}

describe("findDraftNodes", () => {
  it("finds fractions, roots, scripts, abs, and groups", () => {
    const nodes = findDraftNodes("$\\frac{8}{8}\\sqrt{x}x^{2}|y|\\sin()$");
    expect(nodes.filter((n) => n.kind !== "text").map((n) => n.kind)).toEqual([
      "frac",
      "sqrt",
      "script",
      "abs",
      "group",
    ]);
  });

  it("keeps an empty binomial, vector, and d/d slot as boxes", () => {
    expect(findDraftNodes("$\\binom{}{}$").some((n) => n.kind === "binom")).toBe(true);
    expect(findDraftNodes("$\\vec{}$").some((n) => n.kind === "vec")).toBe(true);
    expect(findDraftNodes("d{}").some((n) => n.kind === "brace")).toBe(true);
    expect(findDraftNodes("$\\mathrm{rad}$").some((n) => n.kind === "brace")).toBe(false);
  });

  it("keeps \\sin() / \\cos() as one group, not a repeated name", () => {
    const text = "$\\cos()$";
    const nodes = findDraftNodes(text);
    expect(nodes.filter((n) => n.kind === "group")).toHaveLength(1);
    const leftover = nodes
      .filter((n) => n.kind === "text")
      .map((n) => text.slice(n.start, n.end).replace(/\$/g, ""))
      .join("");
    expect(leftover).not.toMatch(/cos|\\cos/i);
  });

  it.each([
    [String.raw`$\sin(x)$`, "sin(", ")"],
    [String.raw`$[x]$`, "[", "]"],
    [String.raw`$\{x\}$`, "{", "}"],
    [String.raw`$\lfloor x\rfloor$`, "⌊", "⌋"],
    [String.raw`$\lceil x \rceil$`, "⌈", "⌉"],
  ])("reads %s as one box drawn %s … %s", (text, open, close) => {
    const groups = findDraftNodes(text).filter((n) => n.kind === "group");
    expect(groups).toHaveLength(1);
    const group = groups[0]!;
    expect(group.kind === "group" && [group.open, group.close]).toEqual([open, close]);
    expect(text.slice(group.body.open + 1, group.body.close).trim()).toBe("x");
  });

  it("keeps the continue caret inside the closing dollar", () => {
    expect(caretAfterExpression("$\\frac{8}{8}$")).toBe("$\\frac{8}{8}$".length - 1);
  });
});

describe("spliceMathBackspace", () => {
  it("deletes a denominator digit without exposing raw \\frac braces", () => {
    const text = "$\\frac{8}{8}$";
    const den = text.lastIndexOf("8") + 1;
    const once = spliceMathBackspace(text, { start: den, end: den });
    expect(once.text).toBe("$\\frac{8}{}$");
    const twice = spliceMathBackspace(once.text, once.selection);
    expect(twice.text).toBe("$\\frac{}{}$");
    const gone = spliceMathBackspace(twice.text, twice.selection);
    expect(gone.text).toBe("");
  });

  it("deletes \\times after a fraction instead of the closing brace", () => {
    const text = "$\\frac{8}{8}\\times $";
    const caret = text.length - 1;
    const result = spliceMathBackspace(text, { start: caret, end: caret });
    expect(result.text).toBe("$\\frac{8}{8}$");
  });

  it("deletes the first numerator digit when the caret is at the front", () => {
    const text = "$\\frac{8}{8}$";
    const result = spliceMathBackspace(text, { start: 1, end: 1 });
    expect(result.text).toBe("$\\frac{}{8}$");
  });

  it("deletes inside a nested superscript instead of the closing brace", () => {
    const text = "$\\frac{d^{2}}{dx^{2}}$";
    const result = spliceMathBackspace(text, { start: text.length - 1, end: text.length - 1 });
    expect(result.text).toBe("$\\frac{d^{2}}{dx^{}}$");
    let state = result;
    const seen = [state.text];
    while (state.text) {
      state = spliceMathBackspace(state.text, state.selection);
      seen.push(state.text);
      if (seen.length > 16) break;
    }
    expect(seen.at(-1)).toBe("");
    expect(seen.join("\n")).not.toMatch(/\\frac[^}]*$/m);
  });

  it("deletes a unit command as one key", () => {
    const text = "$\\mathrm{rad}$";
    const result = spliceMathBackspace(text, { start: text.length - 1, end: text.length - 1 });
    expect(result.text).toBe("");
  });

  it("deletes a binomial as one key", () => {
    const text = "$\\binom{}{}$";
    const result = spliceMathBackspace(text, { start: text.length - 1, end: text.length - 1 });
    expect(result.text).toBe("");
  });

  it("deletes a thin space with its differential", () => {
    const text = "$\\,dx$";
    let state = spliceMathBackspace(text, { start: text.length - 1, end: text.length - 1 });
    const seen = [state.text];
    while (state.text) {
      state = spliceMathBackspace(state.text, state.selection);
      seen.push(state.text);
      if (seen.length > 6) break;
    }
    expect(seen).not.toContain("$\\$");
    expect(state.text).toBe("");
  });

  it("deletes a finished fraction from the trailing dollar without leaking latex", () => {
    const text = "$\\frac{8}{8}$";
    const result = spliceMathBackspace(text, { start: text.length - 1, end: text.length - 1 });
    expect(result.text).toBe("$\\frac{8}{}$");
  });

  it.each([
    ["$\\cos()$", "$\\cos()$".length - 1, ""],
    ["$\\sin()$", "$\\sin()$".length - 1, ""],
    ["$\\sqrt{}$", "$\\sqrt{}$".length - 1, ""],
    ["$x^{}$", "$x^{}$".length - 1, "$x$"],
    ["$x_{}$", "$x_{}$".length - 1, "$x$"],
    ["$||$", "$||$".length - 1, ""],
    ["$[]$", "$[]$".length - 1, ""],
    ["$\\{\\}$", "$\\{\\}$".length - 1, ""],
    ["$\\lfloor \\rfloor$", "$\\lfloor \\rfloor$".length - 1, ""],
    ["$\\lceil \\rceil$", "$\\lceil \\rceil$".length - 1, ""],
  ])("peels empty %s without leaking latex", (text, caret, expected) => {
    const result = spliceMathBackspace(text, { start: caret, end: caret });
    expect(result.text).toBe(expected);
    expect(result.text).not.toMatch(/\\(cos|sin|sqrt|frac|lfloor|rfloor|lceil|rceil)\b/);
    expect(result.text).not.toMatch(/[{}]/);
  });

  const DIGIT = MATH_KEYBOARD_SYMBOLS.find((spec) => spec.id === "digit-1")
    ?? { id: "digit-1", label: "1", insert: "1", cursorOffset: 1, group: "pad" as const };

  it.each([
    ["brackets", "$[1]$", "$[]$"],
    ["braces", "$\\{1\\}$", "$\\{\\}$"],
    ["floor", "$\\lfloor 1\\rfloor$", "$\\lfloor \\rfloor$"],
    ["ceil", "$\\lceil 1\\rceil$", "$\\lceil \\rceil$"],
  ])("types a digit inside %s, then deletes the pair together", (id, typedText, emptyText) => {
    const spec = MATH_KEYBOARD_SYMBOLS.find((item) => item.id === id)!;
    const opened = spliceMathInsert("", { start: 0, end: 0 }, spec);
    const typed = spliceMathInsert(opened.text, opened.selection, DIGIT);
    expect(typed.text).toBe(typedText);
    const withoutDigit = spliceMathBackspace(typed.text, typed.selection);
    expect(withoutDigit.text).toBe(emptyText);
    const gone = spliceMathBackspace(withoutDigit.text, withoutDigit.selection);
    expect(gone.text).toBe("");
  });

  /** Every `\lfloor` keeps its `\rfloor`, and every `\lceil` its `\rceil`. */
  function pairsWhole(text: string): boolean {
    const count = (re: RegExp) => (text.match(re) ?? []).length;
    return count(/\\lfloor/g) === count(/\\rfloor/g) && count(/\\lceil/g) === count(/\\rceil/g);
  }

  it.each([
    [["floor", "floor"]],
    [["floor", "ceil"]],
    [["sqrt", "floor"]],
    [["floor", "frac"]],
  ])("never leaves half a pair deleting %j around a digit", (ids) => {
    let state = { text: "", selection: { start: 0, end: 0 } };
    for (const id of [...ids, "digit-1"]) {
      const spec = id === "digit-1" ? DIGIT : MATH_KEYBOARD_SYMBOLS.find((item) => item.id === id)!;
      state = spliceMathInsert(state.text, state.selection, spec);
    }
    const seen = [state.text];
    while (state.text && seen.length < 12) {
      state = spliceMathBackspace(state.text, state.selection);
      seen.push(state.text);
    }
    expect(state.text).toBe("");
    expect(seen.filter((text) => !pairsWhole(text))).toEqual([]);
  });

  it.each([
    // ceil, x, →, 2, y, then the 2 deleted: `\rceily` would be a command, not ⌈x⌉y.
    [String.raw`$\lceil x\rceil2‸y$`, [String.raw`$\lceil x\rceil ‸y$`, String.raw`$\lceil ‸\rceil y$`, "$‸y$", "‸"]],
    // floor, x, →, y: the space the y was given stays with the pair.
    [String.raw`$\lfloor x\rfloor y‸$`, [String.raw`$\lfloor x\rfloor ‸$`, String.raw`$\lfloor ‸\rfloor $`, "‸"]],
  ])("never joins a letter to a closer's name deleting %s", (marked, drafts) => {
    expect(backspaces(marked)).toEqual(drafts);
  });

  it("BUG FIX regression: collapseEmptyMath does not corrupt $$display math$$ with content (KB-040)", () => {
    // Backspace inside display math should NOT strip the $$ delimiters when
    // there's content between them. Position 3 (^) deleted → "$$x2$$" (still has $$).
    const text = "$$x^2$$";
    const result = spliceMathBackspace(text, { start: 4, end: 4 });
    expect(result.text).toBe("$$x2$$");
    // The $$ delimiters are preserved because there's still content inside.
    expect(result.text).toContain("$$");
  });
});

describe("a template inside a box", () => {
  // `‸` is the caret. Every kind of box, a bracket pair included, holds every kind of template.
  const BOXES: [string, string][] = [
    [String.raw`\lfloor `, String.raw`\rfloor`],
    [String.raw`\lceil `, String.raw`\rceil`],
    [String.raw`\{`, String.raw`\}`],
    [String.raw`\sqrt{`, "}"],
    [String.raw`\frac{1}{`, "}"],
    [String.raw`\sin(`, ")"],
    ["[", "]"],
  ];
  const BEHIND = [
    String.raw`\frac{1}{2}‸`,
    String.raw`\frac{1‸}{2}`,
    String.raw`\sqrt{2}‸`,
    String.raw`\sqrt[3]{8}‸`,
    String.raw`\binom{5}{2}‸`,
    String.raw`\vec{v}‸`,
    "x^{2}‸",
    "(x)‸",
    "|x|‸",
    String.raw`\{1\}‸`,
    String.raw`\lfloor 3\rfloor‸`,
    String.raw`\lceil 3\rceil‸`,
  ];
  const AHEAD = [
    String.raw`‸\frac{1}{2}`,
    String.raw`‸\sqrt{2}`,
    "‸(x)",
    "‸|x|",
    String.raw`‸\{x\}`,
    String.raw`‸\lfloor x\rfloor`,
    String.raw`‸\lceil x\rceil`,
    String.raw`‸\frac{12}{3}`,
  ];
  const cases = (templates: string[]) =>
    BOXES.flatMap(([open, close]) => templates.map((template) => [open, close, template] as const));

  /** Each press in the box leaves the draft and caret the same press leaves on the template alone. */
  function peelsAsAlone(open: string, close: string, template: string): void {
    const alone = backspaces(`$${template}$`);
    expect(alone.at(-1)).toBe("‸");
    const inBox = backspaces(`$${open}${template}${close}$`, alone.length);
    const boxed = (draft: string) => `$${open}${draft === "‸" ? draft : draft.slice(1, -1)}${close}$`;
    expect(inBox).toEqual(alone.map(boxed));
  }

  it.each(cases(BEHIND))("in %s…%s, peels %s press by press as it does on its own", peelsAsAlone);

  it.each(cases(AHEAD))("in %s…%s, deletes forward into %s as it does on its own", peelsAsAlone);

  it.each([
    [String.raw`$\lfloor \frac{1}{2}‸\rfloor$`, String.raw`$\lfloor \frac{1}{‸}\rfloor$`],
    [String.raw`$\lfloor \frac{1‸}{2}\rfloor$`, String.raw`$\lfloor \frac{‸}{2}\rfloor$`],
    [String.raw`$\lfloor \sqrt{2}‸\rfloor$`, String.raw`$\lfloor \sqrt{‸}\rfloor$`],
    [String.raw`$\lfloor \binom{5}{2}‸\rfloor$`, String.raw`$\lfloor \binom{5}{‸}\rfloor$`],
    [String.raw`$\{\frac{1}{2}‸\}$`, String.raw`$\{\frac{1}{‸}\}$`],
    [String.raw`$\sqrt{\frac{1}{2}‸}$`, String.raw`$\sqrt{\frac{1}{‸}}$`],
    [String.raw`$(\frac{1}{2}‸)$`, String.raw`$(\frac{1}{‸})$`],
    [String.raw`$\sqrt{‸\lfloor x\rfloor}$`, String.raw`$\sqrt{\lfloor ‸\rfloor}$`],
    [String.raw`$\frac{1}{‸\lfloor x\rfloor}$`, String.raw`$\frac{1}{\lfloor ‸\rfloor}$`],
    [String.raw`$\sqrt{‸(x)}$`, String.raw`$\sqrt{(‸)}$`],
    [String.raw`$\sqrt{‸\frac{12}{3}}$`, String.raw`$\sqrt{\frac{‸2}{3}}$`],
  ])("deletes one token of %s and keeps the caret in its box", (marked, expected) => {
    expect(backspaces(marked, 1)).toEqual([expected]);
  });

  it.each([
    [String.raw`$\sqrt{\frac{1}{2}‸}$`, String.raw`$\sqrt{\frac{1}{3}}$`],
    [String.raw`$\lfloor \frac{1}{2}‸\rfloor$`, String.raw`$\lfloor \frac{1}{3}\rfloor$`],
    [String.raw`$(\frac{1}{2}‸)$`, String.raw`$(\frac{1}{3})$`],
  ])("types the next key into the box backspace left in %s", (marked, expected) => {
    const three = MATH_KEYBOARD_SYMBOLS.find((spec) => spec.id === "digit-3")
      ?? { id: "digit-3", label: "3", insert: "3", cursorOffset: 1, group: "pad" as const };
    const deleted = spliceMathBackspace(unmark(marked).text, unmark(marked).selection);
    expect(spliceMathInsert(deleted.text, deleted.selection, three).text).toBe(expected);
  });
});

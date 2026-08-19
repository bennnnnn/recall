import {
  autoAdvanceFracDen,
  caretForInsert,
  caretInGroup,
  findFracSlots,
  fracTapAdvancesToDen,
  isCursorInsideInlineMath,
  MATH_KEYBOARD_SYMBOLS,
  MATH_NUMPAD_ROWS,
  mathGroupCanToggleDigits,
  mathGroupShowsNumpad,
  nextEditSlotCaret,
  prevEditSlotCaret,
  spliceBackspace,
  spliceMathInsert,
} from "@/lib/mathKeyboardSymbols";

describe("spliceMathInsert", () => {
  it("wraps a snippet in $...$ when the caret is outside math", () => {
    const frac = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "frac")!;
    const result = spliceMathInsert("ab", { start: 1, end: 1 }, frac);
    expect(result.text).toBe("a$\\frac{}{}$b");
    expect(result.selection).toEqual({ start: 8, end: 8 });
  });

  it("does not add a second $ pair inside an open math span", () => {
    const sqrt = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "sqrt")!;
    const result = spliceMathInsert("$x+$", { start: 3, end: 3 }, sqrt);
    expect(result.text).toBe("$x+\\sqrt{}$");
    expect(isCursorInsideInlineMath("$x+$", 3)).toBe(true);
    expect(result.selection.start).toBe(9);
  });

  it("replaces the current selection", () => {
    const pi = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "pi")!;
    const result = spliceMathInsert("foo", { start: 0, end: 3 }, pi);
    expect(result.text).toBe("$\\pi $");
  });

  it("places a following digit in the numerator, then the denominator after jumping slots", () => {
    const frac = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "frac")!;
    const one = { id: "digit-1", label: "1", insert: "1", cursorOffset: 1, group: "pad" as const };
    const two = { id: "digit-2", label: "2", insert: "2", cursorOffset: 1, group: "pad" as const };
    const afterFrac = spliceMathInsert("", { start: 0, end: 0 }, frac);
    expect(afterFrac.text).toBe("$\\frac{}{}$");
    const slots = findFracSlots(afterFrac.text);
    expect(caretInGroup(afterFrac.selection.start, slots[0]!.num)).toBe(true);
    const afterNum = spliceMathInsert(afterFrac.text, afterFrac.selection, one);
    expect(afterNum.text).toBe("$\\frac{1}{}$");
    const denAfterNum = findFracSlots(afterNum.text)[0]!.den;
    const afterDen = spliceMathInsert(afterNum.text, { start: denAfterNum.close, end: denAfterNum.close }, two);
    expect(afterDen.text).toBe("$\\frac{1}{2}$");
  });

  it("keeps every symbol cursor inside the insert snippet", () => {
    for (const spec of MATH_KEYBOARD_SYMBOLS) {
      expect(spec.cursorOffset).toBeGreaterThanOrEqual(0);
      expect(spec.cursorOffset).toBeLessThanOrEqual(spec.insert.length);
    }
  });

  it("ⁿ√ inserts an nth-root index, not n times square root", () => {
    const nroot = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "nroot")!;
    expect(nroot.insert).toBe("\\sqrt[]{}");
    expect(spliceMathInsert("", { start: 0, end: 0 }, nroot).text).toBe("$\\sqrt[]{}$");
  });

  it("Calc √[n] inserts an nth-root index slot", () => {
    const nth = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "nth")!;
    expect(nth.insert).toBe("\\sqrt[]{}");
    expect(spliceMathInsert("", { start: 0, end: 0 }, nth).text).toBe("$\\sqrt[]{}$");
  });

  it("n! attaches to a number, or inserts n on an empty draft", () => {
    const fact = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "fact")!;
    expect(spliceMathInsert("", { start: 0, end: 0 }, fact).text).toBe("$n!$");
    expect(spliceMathInsert("$5$", { start: 2, end: 2 }, fact).text).toBe("$5!$");
  });

  it("xⁿ inserts a base x and an exponent box, or attaches ^ to an existing base", () => {
    const sup = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "sup")!;
    expect(spliceMathInsert("", { start: 0, end: 0 }, sup).text).toBe("$x^{}$");
    expect(spliceMathInsert("$2$", { start: 2, end: 2 }, sup).text).toBe("$2^{}$");
    expect(spliceMathInsert("$x$", { start: 2, end: 2 }, sup).text).toBe("$x^{}$");
  });

  it("digits stay prose inside a convert draft", () => {
    const one = { id: "digit-1", label: "1", insert: "1", cursorOffset: 1, group: "pad" as const };
    const typed = spliceMathInsert("convert  km to mi", { start: 8, end: 8 }, one);
    expect(typed.text).toBe("convert 1 km to mi");
    expect(typed.text).not.toContain("$");
  });
});

describe("key insert matches the button", () => {
  it.each([
    ["frac", "\\frac{}{}"],
    ["sqrt", "\\sqrt{}"],
    ["nroot", "\\sqrt[]{}"],
    ["sup", "x^{}"],
    ["sub", "x_{}"],
    ["abs", "||"],
    ["pi", "\\pi "],
    ["leq", "\\leq "],
    ["geq", "\\geq "],
    ["neq", "\\neq "],
    ["lt", "<"],
    ["gt", ">"],
    ["times", "\\times "],
    ["div", "\\div "],
    ["plus", "+"],
    ["minus", "-"],
    ["eq", "="],
    ["parens", "()"],
    ["sin", "\\sin()"],
    ["cos", "\\cos()"],
    ["tan", "\\tan()"],
    ["cot", "\\cot()"],
    ["sec", "\\sec()"],
    ["csc", "\\csc()"],
    ["arcsin", "\\arcsin()"],
    ["arccos", "\\arccos()"],
    ["arctan", "\\arctan()"],
    ["arccot", "\\cot^{-1}()"],
    ["arcsec", "\\sec^{-1}()"],
    ["arccsc", "\\csc^{-1}()"],
    ["rad", "\\mathrm{rad}"],
    ["arcsinh", "\\sinh^{-1}()"],
    ["arccosh", "\\cosh^{-1}()"],
    ["arctanh", "\\tanh^{-1}()"],
    ["log", "\\log()"],
    ["ln", "\\ln()"],
    ["logn", "\\log_{}()"],
    ["exp", "\\exp()"],
    ["tenpow", "10^{}"],
    ["sinh", "\\sinh()"],
    ["cosh", "\\cosh()"],
    ["tanh", "\\tanh()"],
    ["deg", "^{\\circ}"],
    ["int", "\\int "],
    ["dint", "\\int_{}^{}"],
    ["iint", "\\iint "],
    ["nth", "\\sqrt[]{}"],
    ["sum", "\\sum_{}^{}"],
    ["prod", "\\prod_{}^{}"],
    ["lim", "\\lim_{}"],
    ["infty", "\\infty "],
    ["partial", "\\partial "],
    ["der", "\\frac{d}{dx}"],
    ["der2", "\\frac{d^{2}}{dx^{2}}"],
    ["to", "\\to "],
    ["dx", "\\,dx"],
    ["pm", "\\pm "],
    ["approx", "\\approx "],
    ["binom", "\\binom{}{}"],
    ["percent", "\\%"],
    ["euler", "e"],
    ["imag", "i"],
    ["alpha", "\\alpha "],
    ["beta", "\\beta "],
    ["gamma", "\\gamma "],
    ["delta", "\\delta "],
    ["epsilon", "\\varepsilon "],
    ["zeta", "\\zeta "],
    ["eta", "\\eta "],
    ["theta", "\\theta "],
    ["kappa", "\\kappa "],
    ["lambda", "\\lambda "],
    ["mu", "\\mu "],
    ["nu", "\\nu "],
    ["xi", "\\xi "],
    ["pi-greek", "\\pi "],
    ["rho", "\\rho "],
    ["sigma", "\\sigma "],
    ["tau", "\\tau "],
    ["phi", "\\phi "],
    ["chi", "\\chi "],
    ["psi", "\\psi "],
    ["omega", "\\omega "],
    ["Gamma", "\\Gamma "],
    ["Delta", "\\Delta "],
    ["Sigma", "\\Sigma "],
    ["Omega", "\\Omega "],
  ] as const)("%s inserts %s", (id, insert) => {
    const spec = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === id);
    expect(spec?.insert).toBe(insert);
  });
});

describe("slot navigation", () => {
  it("advances from a filled numerator to an empty denominator", () => {
    const text = "$\\frac{1}{}$";
    const slots = findFracSlots(text);
    expect(nextEditSlotCaret(text, slots[0]!.num.close)).toBe(slots[0]!.den.close);
    expect(fracTapAdvancesToDen(text, slots[0]!.num.close)).toBe(slots[0]!.den.close);
  });

  it("auto-advances after inserting pi into an empty numerator", () => {
    const frac = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "frac")!;
    const pi = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "pi")!;
    const afterFrac = spliceMathInsert("", { start: 0, end: 0 }, frac);
    const afterPi = spliceMathInsert(afterFrac.text, afterFrac.selection, pi);
    const jump = autoAdvanceFracDen(
      afterFrac.text,
      afterFrac.selection.start,
      afterPi.text,
      afterPi.selection.start,
      pi,
    );
    expect(jump).not.toBeNull();
    expect(caretInGroup(jump!, findFracSlots(afterPi.text)[0]!.den)).toBe(true);
  });

  it("does not auto-advance after a digit so multi-digit numerators stay possible", () => {
    const frac = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "frac")!;
    const one = { id: "digit-1", label: "1", insert: "1", cursorOffset: 1, group: "pad" as const };
    const afterFrac = spliceMathInsert("", { start: 0, end: 0 }, frac);
    const afterOne = spliceMathInsert(afterFrac.text, afterFrac.selection, one);
    expect(
      autoAdvanceFracDen(
        afterFrac.text,
        afterFrac.selection.start,
        afterOne.text,
        afterOne.selection.start,
        one,
      ),
    ).toBeNull();
  });

  it("second fraction tap jumps to an empty denominator instead of nesting", () => {
    const frac = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "frac")!;
    const one = { id: "digit-1", label: "1", insert: "1", cursorOffset: 1, group: "pad" as const };
    const afterFrac = spliceMathInsert("", { start: 0, end: 0 }, frac);
    const afterOne = spliceMathInsert(afterFrac.text, afterFrac.selection, one);
    const jump = fracTapAdvancesToDen(afterOne.text, afterOne.selection.start);
    expect(jump).toBe(findFracSlots(afterOne.text)[0]!.den.close);
  });

  it("exits a filled last box instead of wrapping back to the first", () => {
    const text = "$\\frac{8}{8}$";
    const slots = findFracSlots(text);
    expect(nextEditSlotCaret(text, slots[0]!.den.close)).toBe(slots[0]!.den.close + 1);
  });

  it("places × after a finished fraction, not inside the denominator", () => {
    const times = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "times")!;
    const text = "$\\frac{8}{8}$";
    const den = findFracSlots(text)[0]!.den;
    const at = caretForInsert(text, den.close, times);
    const result = spliceMathInsert(text, { start: at, end: at }, times);
    expect(result.text).toBe("$\\frac{8}{8}\\times $");
  });
});

describe("spliceBackspace", () => {
  it("deletes the selection or the previous character", () => {
    expect(spliceBackspace("abc", { start: 3, end: 3 })).toEqual({
      text: "ab",
      selection: { start: 2, end: 2 },
    });
    expect(spliceBackspace("abc", { start: 1, end: 3 })).toEqual({
      text: "a",
      selection: { start: 1, end: 1 },
    });
  });
});

describe("mathGroupShowsNumpad", () => {
  it("keeps digits on Basics only", () => {
    expect(mathGroupShowsNumpad("basics")).toBe(true);
    expect(mathGroupShowsNumpad("trig")).toBe(false);
    expect(mathGroupShowsNumpad("calc")).toBe(false);
    expect(mathGroupShowsNumpad("greek")).toBe(false);
  });
});

describe("mathGroupCanToggleDigits", () => {
  it("offers 123 on symbol tabs that hide the number pad", () => {
    expect(mathGroupCanToggleDigits("trig")).toBe(true);
    expect(mathGroupCanToggleDigits("calc")).toBe(true);
    expect(mathGroupCanToggleDigits("greek")).toBe(true);
    expect(mathGroupCanToggleDigits("basics")).toBe(false);
    expect(mathGroupCanToggleDigits("converter")).toBe(false);
  });
});

describe("MATH_NUMPAD_ROWS", () => {
  it("is a calculator grid with comma, y, backspace, and slot nav", () => {
    expect(MATH_NUMPAD_ROWS).toHaveLength(4);
    const ids = MATH_NUMPAD_ROWS.flat().flatMap((c) =>
      c.kind === "insert" ? [c.spec.id] : [],
    );
    expect(ids).toContain("comma");
    expect(ids).toContain("var-y");
    expect(MATH_NUMPAD_ROWS.flat().some((c) => c.kind === "backspace")).toBe(true);
    expect(MATH_NUMPAD_ROWS.flat().some((c) => c.kind === "slot-nav")).toBe(true);
  });

  it("BUG FIX regression: includes <, >, and extra variables (z, n, t)", () => {
    const allSymbols = MATH_KEYBOARD_SYMBOLS.map((s) => s.id);
    expect(allSymbols).toContain("lt");
    expect(allSymbols).toContain("gt");
    const padIds = MATH_NUMPAD_ROWS.flat().flatMap((c) =>
      c.kind === "insert" ? [c.spec.id] : [],
    );
    expect(padIds).toContain("var-z");
    expect(padIds).toContain("var-n");
    expect(padIds).toContain("var-t");
  });
});

describe("nextEditSlotCaret / prevEditSlotCaret", () => {
  it("moves numerator → denominator → back", () => {
    const text = "$\\frac{1}{}$";
    const slots = findFracSlots(text)[0]!;
    const den = nextEditSlotCaret(text, slots.num.close);
    expect(den).toBe(slots.den.close);
    expect(prevEditSlotCaret(text, den!)).toBe(slots.num.close);
  });
});

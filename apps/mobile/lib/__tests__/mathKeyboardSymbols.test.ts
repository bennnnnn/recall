import {
  autoAdvanceFracDen,
  autoAdvanceNextEmptySlot,
  caretForInsert,
  caretInGroup,
  converterResultSpec,
  findFracSlots,
  findLognSlots,
  findNrootSlots,
  fracTapAdvancesToDen,
  isCursorInsideInlineMath,
  MATH_KEYBOARD_SYMBOLS,
  MATH_NUMPAD_ROWS,
  MATH_SYMBOL_ROW_SIZE,
  mathGroupCanToggleDigits,
  mathGroupShowsNumpad,
  nextEditSlotCaret,
  prevEditSlotCaret,
  spliceBackspace,
  spliceMathInsert,
  SYMBOL_A11Y,
  symbolA11yLabel,
  symbolsInGroup,
  symbolRowsForGroup,
  tapAdvancesToNextSlot,
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

  it("n! attaches to a number, or inserts an empty slot on an empty draft", () => {
    const fact = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "fact")!;
    expect(spliceMathInsert("", { start: 0, end: 0 }, fact).text).toBe("${}!$");
    expect(spliceMathInsert("$5$", { start: 2, end: 2 }, fact).text).toBe("$5!$");
  });

  it("xⁿ inserts a base x and an exponent box, or attaches ^ to an existing base", () => {
    const sup = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "sup")!;
    expect(spliceMathInsert("", { start: 0, end: 0 }, sup).text).toBe("$x^{}$");
    expect(spliceMathInsert("$2$", { start: 2, end: 2 }, sup).text).toBe("$2^{}$");
    expect(spliceMathInsert("$x$", { start: 2, end: 2 }, sup).text).toBe("$x^{}$");
  });

  it("eⁿ inserts Euler's number with an exponent box", () => {
    const euler = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "euler")!;
    const result = spliceMathInsert("", { start: 0, end: 0 }, euler);
    expect(result.text).toBe("$e^{}$");
    expect(result.text[result.selection.start]).toBe("}");
  });

  it("d/d□ lands in the variable slot", () => {
    const ddv = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "ddv")!;
    const result = spliceMathInsert("", { start: 0, end: 0 }, ddv);
    expect(result.text).toBe("$\\frac{d}{d{}}$");
    expect(result.text.slice(result.selection.start - 1, result.selection.start + 1)).toBe("{}");
  });

  it("° attaches to a number, or inserts a base box on an empty draft", () => {
    const deg = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "deg")!;
    const empty = spliceMathInsert("", { start: 0, end: 0 }, deg);
    expect(empty.text).toBe("$^{\\circ}$");
    expect(empty.text[empty.selection.start]).toBe("^");
    const typed = spliceMathInsert(empty.text, empty.selection, {
      id: "digit-3",
      label: "3",
      insert: "3",
      cursorOffset: 1,
      group: "pad" as const,
    });
    expect(typed.text).toBe("$3^{\\circ}$");
    expect(spliceMathInsert("$30$", { start: 3, end: 3 }, deg).text).toBe("$30^{\\circ}$");
  });

  it("labels second derivative as d²/dx²", () => {
    expect(MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "der2")?.label).toBe("d²/dx²");
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
    ["trig-theta", "\\theta "],
    ["trig-pi", "\\pi "],
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
    ["euler", "e^{}"],
    ["imag", "i"],
    ["oint", "\\oint "],
    ["iiint", "\\iiint "],
    ["nabla", "\\nabla "],
    ["vec", "\\vec{}"],
    ["cdot", "\\cdot "],
    ["ddv", "\\frac{d}{d{}}"],
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

  it("auto-advances from a filled nth-root index into the radicand", () => {
    const nroot = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "nroot")!;
    const pi = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "pi")!;
    const afterRoot = spliceMathInsert("", { start: 0, end: 0 }, nroot);
    expect(caretInGroup(afterRoot.selection.start, findNrootSlots(afterRoot.text)[0]!.index)).toBe(
      true,
    );
    const afterPi = spliceMathInsert(afterRoot.text, afterRoot.selection, pi);
    const jump = autoAdvanceNextEmptySlot(
      afterRoot.text,
      afterRoot.selection.start,
      afterPi.text,
      afterPi.selection.start,
      pi,
    );
    expect(jump).not.toBeNull();
    expect(caretInGroup(jump!, findNrootSlots(afterPi.text)[0]!.radicand)).toBe(true);
  });

  it("does not auto-advance an nth-root index after a digit", () => {
    const nroot = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "nroot")!;
    const three = { id: "digit-3", label: "3", insert: "3", cursorOffset: 1, group: "pad" as const };
    const afterRoot = spliceMathInsert("", { start: 0, end: 0 }, nroot);
    const afterThree = spliceMathInsert(afterRoot.text, afterRoot.selection, three);
    expect(
      autoAdvanceNextEmptySlot(
        afterRoot.text,
        afterRoot.selection.start,
        afterThree.text,
        afterThree.selection.start,
        three,
      ),
    ).toBeNull();
    expect(
      tapAdvancesToNextSlot(afterThree.text, afterThree.selection.start, "nroot"),
    ).toBe(findNrootSlots(afterThree.text)[0]!.radicand.close);
  });

  it("auto-advances from a filled logₙ base into the argument", () => {
    const logn = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "logn")!;
    const pi = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "pi")!;
    const afterLog = spliceMathInsert("", { start: 0, end: 0 }, logn);
    expect(caretInGroup(afterLog.selection.start, findLognSlots(afterLog.text)[0]!.base)).toBe(
      true,
    );
    const afterPi = spliceMathInsert(afterLog.text, afterLog.selection, pi);
    const jump = autoAdvanceNextEmptySlot(
      afterLog.text,
      afterLog.selection.start,
      afterPi.text,
      afterPi.selection.start,
      pi,
    );
    expect(jump).not.toBeNull();
    expect(caretInGroup(jump!, findLognSlots(afterPi.text)[0]!.arg)).toBe(true);
  });

  it("second logₙ tap jumps from a filled base into the empty argument", () => {
    const logn = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "logn")!;
    const two = { id: "digit-2", label: "2", insert: "2", cursorOffset: 1, group: "pad" as const };
    const afterLog = spliceMathInsert("", { start: 0, end: 0 }, logn);
    const afterTwo = spliceMathInsert(afterLog.text, afterLog.selection, two);
    expect(tapAdvancesToNextSlot(afterTwo.text, afterTwo.selection.start, "logn")).toBe(
      findLognSlots(afterTwo.text)[0]!.arg.close,
    );
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
  it("is a 6-column calculator grid with comma, y, backspace", () => {
    expect(MATH_NUMPAD_ROWS).toHaveLength(4);
    expect(MATH_NUMPAD_ROWS.every((row) => row.length === MATH_SYMBOL_ROW_SIZE)).toBe(true);
    const ids = MATH_NUMPAD_ROWS.flat().flatMap((c) =>
      c.kind === "insert" ? [c.spec.id] : [],
    );
    expect(ids).toContain("comma");
    expect(ids).toContain("var-y");
    expect(MATH_NUMPAD_ROWS.flat().some((c) => c.kind === "backspace")).toBe(true);
    expect(MATH_NUMPAD_ROWS.flat().some((c) => c.kind === "prev")).toBe(true);
    expect(MATH_NUMPAD_ROWS.flat().some((c) => c.kind === "next")).toBe(true);
  });

  it("BUG FIX regression: includes <, >, and variable z", () => {
    const allSymbols = MATH_KEYBOARD_SYMBOLS.map((s) => s.id);
    expect(allSymbols).toContain("lt");
    expect(allSymbols).toContain("gt");
    const padIds = MATH_NUMPAD_ROWS.flat().flatMap((c) =>
      c.kind === "insert" ? [c.spec.id] : [],
    );
    expect(padIds).toContain("var-z");
  });
});

describe("symbol homes (no duplicate glyphs)", () => {
  it("keeps π on Basics, θ on Greek, and ⁿ√ only on Basics", () => {
    const homes = (id: string) => MATH_KEYBOARD_SYMBOLS.filter((s) => s.id === id).map((s) => s.group);
    expect(homes("pi")).toEqual(["basics"]);
    expect(homes("theta")).toEqual(["greek"]);
    expect(homes("nroot")).toEqual(["basics"]);
    expect(MATH_KEYBOARD_SYMBOLS.some((s) => s.id === "nth")).toBe(false);
    expect(symbolsInGroup("trig").some((s) => s.id === "trig-pi" || s.id === "trig-theta")).toBe(
      false,
    );
    expect(MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "trig-pi")?.group).toBe("pad");
    expect(MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "trig-theta")?.group).toBe("pad");
    expect(MATH_KEYBOARD_SYMBOLS.some((s) => s.id === "pi-greek")).toBe(false);
  });

  it("fills Calc and Greek in even 6-wide rows", () => {
    expect(symbolsInGroup("calc")).toHaveLength(30);
    expect(symbolsInGroup("calc").length % MATH_SYMBOL_ROW_SIZE).toBe(0);
    expect(symbolsInGroup("greek").length % MATH_SYMBOL_ROW_SIZE).toBe(0);
  });

  it("keeps Trig keys 6-wide by putting 1–0 in leftover cells", () => {
    const rows = symbolRowsForGroup("trig");
    expect(symbolsInGroup("trig")).toHaveLength(20);
    expect(rows.every((row) => row.length === MATH_SYMBOL_ROW_SIZE)).toBe(true);
    const lastFn = rows[3]!;
    expect(lastFn[0]).toMatchObject({ kind: "insert", spec: { id: "arccosh" } });
    expect(lastFn[1]).toMatchObject({ kind: "insert", spec: { id: "arctanh" } });
    expect(lastFn[2]).toMatchObject({ kind: "insert", spec: { id: "digit-1" } });
    expect(lastFn[5]).toMatchObject({ kind: "insert", spec: { id: "digit-4" } });
    const digits = rows[4]!;
    expect(digits.map((c) => (c.kind === "insert" ? c.spec.id : c.kind))).toEqual([
      "digit-5",
      "digit-6",
      "digit-7",
      "digit-8",
      "digit-9",
      "digit-0",
    ]);
  });

  it("inserts a converter result as math with a unit", () => {
    const spec = converterResultSpec("100", "cm");
    expect(spec.insert).toBe("100\\,\\text{cm}");
    expect(spliceMathInsert("", { start: 0, end: 0 }, spec).text).toBe("$100\\,\\text{cm}$");
  });
});

describe("symbolA11yLabel (KB-005)", () => {
  it("returns a descriptive label for known symbol IDs", () => {
    const frac = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "frac")!;
    expect(symbolA11yLabel(frac)).toBe("Fraction");
    const sqrt = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "sqrt")!;
    expect(symbolA11yLabel(sqrt)).toBe("Square root");
    const leq = MATH_KEYBOARD_SYMBOLS.find((s) => s.id === "leq")!;
    expect(symbolA11yLabel(leq)).toBe("Less than or equal");
  });

  it("falls back to the visual label for unknown IDs", () => {
    const fake = { id: "custom", label: "★", insert: "★", cursorOffset: 1, group: "basics" as const };
    expect(symbolA11yLabel(fake)).toBe("★");
  });

  it("covers every symbol in MATH_KEYBOARD_SYMBOLS and MATH_NUMPAD_ROWS", () => {
    const allIds = new Set<string>();
    for (const s of MATH_KEYBOARD_SYMBOLS) allIds.add(s.id);
    for (const row of MATH_NUMPAD_ROWS) {
      for (const cell of row) {
        if (cell.kind === "insert") allIds.add(cell.spec.id);
      }
    }
    const missing = [...allIds].filter((id) => !SYMBOL_A11Y[id]);
    // Digits 0-9 and basic operators on the numpad are self-descriptive labels.
    const allowedMissing = new Set([
      "digit-0", "digit-1", "digit-2", "digit-3", "digit-4",
      "digit-5", "digit-6", "digit-7", "digit-8", "digit-9",
      "plus", "minus", "times", "div", "eq", "parens",
    ]);
    const trulyMissing = missing.filter((id) => !allowedMissing.has(id));
    expect(trulyMissing).toEqual([]);
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

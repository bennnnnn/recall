import {
  autoAdvanceFracDen,
  caretForInsert,
  caretInGroup,
  findFracSlots,
  fracTapAdvancesToDen,
  isCursorInsideInlineMath,
  MATH_KEYBOARD_SYMBOLS,
  MATH_NUMPAD_ROWS,
  nextEditSlotCaret,
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

describe("MATH_NUMPAD_ROWS", () => {
  it("is a 4×5 calculator grid with backspace and next-slot", () => {
    expect(MATH_NUMPAD_ROWS).toHaveLength(4);
    expect(MATH_NUMPAD_ROWS.every((row) => row.length === 5)).toBe(true);
    expect(MATH_NUMPAD_ROWS.flat().some((c) => c.kind === "backspace")).toBe(true);
    expect(MATH_NUMPAD_ROWS.flat().some((c) => c.kind === "next")).toBe(true);
  });
});

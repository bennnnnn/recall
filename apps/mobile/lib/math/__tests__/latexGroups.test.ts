/**
 * One reader of TeX groups (`readGroup`). Seven copies read `{…}` on the phone and three of
 * them counted an escaped brace as structure: `\{1\}` (a set) closed the group around it,
 * so the math keyboard lost a fraction's slots, the input formatter spaced the inside of a
 * `\text{…}`, and Backspace left a dangling brace.
 */
import { findDraftNodes } from "@/lib/math/draftNodes";
import { spliceMathBackspace } from "@/lib/math/draftSlots";
import { formatMathExpr } from "@/lib/math/formatInput";
import { findFracSlots, readBraceGroup, readDelimGroup } from "@/lib/math/keyboardSlots";
import { readGroup } from "@/lib/math/latexGroups";
import { hasIncompleteStreamingLatex } from "@/lib/math/streaming";

describe("readGroup", () => {
  it("reads a group, nested ones inside it, and escaped braces as content", () => {
    expect(readGroup("{a{b}c}d", 0)).toEqual({ value: "a{b}c", next: 7 });
    expect(readGroup("{\\{1\\}}+", 0)).toEqual({ value: "\\{1\\}", next: 7 });
    expect(readGroup("{a\\}", 0)).toBeNull();
    expect(readGroup("x{a}", 0)).toBeNull();
  });

  it("reads a bracket or parenthesis group given its pair", () => {
    expect(readGroup("[3]{x}", 0, "[", "]")).toEqual({ value: "3", next: 3 });
    expect(readGroup("(a(b)\\))", 0, "(", ")")).toEqual({ value: "a(b)\\)", next: 8 });
  });
});

describe("the math keyboard's groups", () => {
  it("closes a brace group at its own brace, not an escaped one", () => {
    expect(readBraceGroup("{a\\}b}", 0)).toEqual({ open: 0, close: 5 });
    expect(readBraceGroup("  {x}", 0)).toEqual({ open: 2, close: 4 });
    expect(readDelimGroup("(a\\)b)", 0, "(", ")")).toEqual({ open: 0, close: 5 });
  });

  it("keeps a fraction's slots when its numerator is a set brace", () => {
    expect(findFracSlots("\\frac{\\{}{2}")).toEqual([{ num: { open: 5, close: 8 }, den: { open: 9, close: 11 } }]);
    expect(findDraftNodes("\\frac{\\{}{2}").map((node) => node.kind)).toEqual(["frac"]);
  });

  it("deletes an escaped brace as one key, never half of it", () => {
    expect(spliceMathBackspace("$x^{a\\}}$", { start: 8, end: 8 }).text).toBe("$x^{a}$");
  });
});

describe("formatting and streaming", () => {
  it("leaves a \\text group whole when it holds an escaped brace", () => {
    expect(formatMathExpr("\\text{a\\}=b}x=3")).toBe("\\text{a\\}=b}x = 3");
  });

  it("waits for a fraction whose arguments are not closed yet", () => {
    expect(hasIncompleteStreamingLatex("\\frac{\\{}{2}")).toBe(false);
    expect(hasIncompleteStreamingLatex("\\frac{\\{}{")).toBe(true);
    expect(hasIncompleteStreamingLatex("\\frac{a\\}")).toBe(true);
  });
});

import { wrapSuggestionMath } from "@/features/suggestions/model/promptMath";

describe("wrapSuggestionMath", () => {
  it("wraps a bare caret equation and leaves the surrounding question", () => {
    expect(
      wrapSuggestionMath(
        "Why does the equation X^2 = 9 have two solutions, +3 and -3, instead of just one?",
      ),
    ).toBe(
      "Why does the equation $X^2 = 9$ have two solutions, +3 and -3, instead of just one?",
    );
  });

  it("wraps each equation in one question", () => {
    expect(
      wrapSuggestionMath(
        "What would the solutions be if the equation was X^2 = 16 instead of X^2 = 9?",
      ),
    ).toBe(
      "What would the solutions be if the equation was $X^2 = 16$ instead of $X^2 = 9$?",
    );
  });

  it("keeps an addition on the same expression", () => {
    expect(
      wrapSuggestionMath("How would you solve the equation X^2 + 4 = 13 using similar steps?"),
    ).toBe("How would you solve the equation $X^2 + 4 = 13$ using similar steps?");
  });

  it("does not wrap a question that is already delimited", () => {
    const ready = "Why does $x^2 = 9$ have two solutions?";
    expect(wrapSuggestionMath(ready)).toBe(ready);
  });

  it("leaves a question with no equation unchanged", () => {
    const plain = "Why does photosynthesis need light?";
    expect(wrapSuggestionMath(plain)).toBe(plain);
  });
});

import { splitAnswerNotation } from "@/lib/answerNotation";

describe("splitAnswerNotation", () => {
  it("keeps an ordinary math answer as math", () => {
    expect(splitAnswerNotation("x = 2")).toEqual({
      notation: "math",
      body: "x = 2",
      labeled: false,
      verified: false,
    });
    expect(splitAnswerNotation("\\frac{1}{2}")).toEqual({
      notation: "math",
      body: "\\frac{1}{2}",
      labeled: false,
      verified: false,
    });
  });

  it("reads a chemistry answer and drops the notation line", () => {
    expect(splitAnswerNotation("notation: chemistry\nM(H2O) = 18.015 g/mol")).toEqual({
      notation: "chemistry",
      body: "M(H2O) = 18.015 g/mol",
      labeled: false,
      verified: false,
    });
  });

  it("keeps a side label and a chemistry notation line", () => {
    expect(splitAnswerNotation("label: answer\nnotation: chemistry\nH2O")).toEqual({
      notation: "chemistry",
      body: "H2O",
      labeled: true,
      verified: false,
    });
  });

  it("does not treat the notation words inside a formula as a tag", () => {
    expect(splitAnswerNotation("notation: chemistry is not a formula")).toEqual({
      notation: "math",
      body: "notation: chemistry is not a formula",
      labeled: false,
      verified: false,
    });
  });

  it("reads the server's verified marker, in any header order", () => {
    expect(splitAnswerNotation("verified: true\nx = 2")).toEqual({
      notation: "math",
      body: "x = 2",
      labeled: false,
      verified: true,
    });
    expect(
      splitAnswerNotation("label: answer\nverified: true\nnotation: chemistry\nH2O"),
    ).toEqual({
      notation: "chemistry",
      body: "H2O",
      labeled: true,
      verified: true,
    });
  });

  it.each(["Verified: TRUE", "verified:true", "verified: yes", "​verified: true"])(
    "accepts only the exact server line as the marker, not %j",
    (forged) => {
      expect(splitAnswerNotation(`${forged}\nx = 7`).verified).toBe(false);
    },
  );

  it("does not take a lone marker for a value", () => {
    expect(splitAnswerNotation("verified: true")).toEqual({
      notation: "math",
      body: "verified: true",
      labeled: false,
      verified: false,
    });
  });
});

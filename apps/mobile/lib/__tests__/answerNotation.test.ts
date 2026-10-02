import { splitAnswerNotation } from "@/lib/answerNotation";

describe("splitAnswerNotation", () => {
  it("keeps an ordinary math answer as math", () => {
    expect(splitAnswerNotation("x = 2")).toEqual({
      notation: "math",
      body: "x = 2",
      labeled: false,
    });
    expect(splitAnswerNotation("\\frac{1}{2}")).toEqual({
      notation: "math",
      body: "\\frac{1}{2}",
      labeled: false,
    });
  });

  it("reads a chemistry answer and drops the notation line", () => {
    expect(splitAnswerNotation("notation: chemistry\nM(H2O) = 18.015 g/mol")).toEqual({
      notation: "chemistry",
      body: "M(H2O) = 18.015 g/mol",
      labeled: false,
    });
  });

  it("keeps a side label and a chemistry notation line", () => {
    expect(splitAnswerNotation("label: answer\nnotation: chemistry\nH2O")).toEqual({
      notation: "chemistry",
      body: "H2O",
      labeled: true,
    });
  });

  it("does not treat the notation words inside a formula as a tag", () => {
    expect(splitAnswerNotation("notation: chemistry is not a formula")).toEqual({
      notation: "math",
      body: "notation: chemistry is not a formula",
      labeled: false,
    });
  });
});

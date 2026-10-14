import {
  arrayText,
  explanationParts,
  formatCell,
  parseArrayFence,
  parseQuizFence,
  quizText,
} from "@/lib/lesson/lessonFences";

const QUIZ = {
  question: "What should `two_sum(nums, target)` return?",
  options: ["`[0, 1]`", "`[1, 2]`", "`[0, 2]`", "`[2, 4]`"],
  answer: 1,
  explanation: "`2 + 4 = 6`, at indexes 1 and 2.",
};

describe("parseQuizFence", () => {
  it("reads the question, options, answer and explanation", () => {
    expect(parseQuizFence(JSON.stringify(QUIZ))).toEqual({
      ...QUIZ,
      label: null,
      code: null,
      codeLang: "python",
    });
  });

  it("reads the label and the code drawn inside the card", () => {
    const fence = parseQuizFence(
      JSON.stringify({
        ...QUIZ,
        label: "Exercise 1",
        code: "\nnumbers = [2, 4]\nprint(numbers)\n",
        lang: "javascript",
      }),
    );
    expect(fence).toMatchObject({
      label: "Exercise 1",
      code: "numbers = [2, 4]\nprint(numbers)",
      codeLang: "javascript",
    });
    expect(quizText(fence!)).toBe(
      "What should `two_sum(nums, target)` return?\nnumbers = [2, 4]\nprint(numbers)\n" +
        "A) `[0, 1]`\nB) `[1, 2]`\nC) `[0, 2]`\nD) `[2, 4]`",
    );
  });

  it.each([
    ["B", 1],
    ["b)", 1],
    ["2", 2],
    ["`[0, 2]`", 2],
  ])("reads the answer %p as option %p", (answer, index) => {
    expect(parseQuizFence(JSON.stringify({ ...QUIZ, answer }))?.answer).toBe(
      index,
    );
  });

  it.each([
    ["not json", "{question"],
    ["no question", JSON.stringify({ ...QUIZ, question: " " })],
    ["one option", JSON.stringify({ ...QUIZ, options: ["only"] })],
    ["an empty option", JSON.stringify({ ...QUIZ, options: ["a", ""] })],
    ["answer out of range", JSON.stringify({ ...QUIZ, answer: 4 })],
    ["unknown answer", JSON.stringify({ ...QUIZ, answer: "the second" })],
  ])("returns null for %s", (_, content) => {
    expect(parseQuizFence(content)).toBeNull();
  });

  it("writes the question and lettered options as text", () => {
    expect(quizText(parseQuizFence(JSON.stringify(QUIZ))!)).toBe(
      "What should `two_sum(nums, target)` return?\nA) `[0, 1]`\nB) `[1, 2]`\nC) `[0, 2]`\nD) `[2, 4]`",
    );
  });
});

describe("parseArrayFence", () => {
  it("reads the name, values and highlighted indexes", () => {
    const fence = parseArrayFence(
      '{"name":"nums","values":[2,7,11,15],"highlight":[0,1,9]}',
    );
    expect(fence).toEqual({
      name: "nums",
      title: null,
      values: [2, 7, 11, 15],
      highlight: [0, 1],
      caption: null,
      note: null,
    });
    expect(arrayText(fence!)).toBe("nums = [2, 7, 11, 15]");
  });

  it("quotes strings and keeps the rest as written", () => {
    expect(formatCell("a")).toBe('"a"');
    expect(formatCell(3.5)).toBe("3.5");
    expect(formatCell(true)).toBe("true");
    expect(arrayText(parseArrayFence('{"values":["a",null]}')!)).toBe(
      '["a", null]',
    );
  });

  it.each([
    ["not json", "[1, 2"],
    ["no values", '{"name":"nums"}'],
    ["empty", '{"values":[]}'],
    ["nested", '{"values":[[1]]}'],
  ])("returns null for %s", (_, content) => {
    expect(parseArrayFence(content)).toBeNull();
  });
});

describe("explanationParts", () => {
  it("splits prose and fenced code in order", () => {
    expect(
      explanationParts(
        "`enumerate()` gives both.\n\n```python\nprint(1)\n```\n\nThen 1 prints.",
      ),
    ).toEqual([
      { kind: "text", text: "`enumerate()` gives both." },
      { kind: "code", lang: "python", code: "print(1)" },
      { kind: "text", text: "Then 1 prints." },
    ]);
  });

  it("keeps plain prose whole", () => {
    expect(explanationParts("Only 6 and 8.")).toEqual([
      { kind: "text", text: "Only 6 and 8." },
    ]);
    expect(explanationParts("")).toEqual([]);
  });
});

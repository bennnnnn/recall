import { fireEvent, render } from "@testing-library/react-native";

import { QuizCard } from "@/components/rich/QuizCard";

jest.mock("@/lib/i18n", () => ({
  __esModule: true,
  default: { t: (key: string) => key },
}));
jest.mock("@/components/CodeBlock", () => {
  const { Text } = jest.requireActual("react-native");
  return {
    CodeBlock: ({ code, lang }: { code: string; lang: string }) => (
      <Text>{`${lang}:${code}`}</Text>
    ),
  };
});
jest.mock("@/lib/haptics", () => ({
  selection: jest.fn(),
  notifySuccess: jest.fn(),
  notifyWarning: jest.fn(),
}));

const quiz = (explanation = "Only 6 and 8 are greater than 4.") =>
  JSON.stringify({
    question: "What will this print?",
    options: ["[2, 4, 6, 8]", "[12, 16]", "[6, 8]"],
    answer: 1,
    explanation,
  });

describe("QuizCard", () => {
  it("checks a right answer and explains it", async () => {
    const view = await render(<QuizCard content={quiz()} />);
    expect(view.getByText("What will this print?")).toBeTruthy();
    expect(view.queryByText("rich.quiz_correct")).toBeNull();
    await fireEvent.press(view.getByText("[12, 16]"));
    await fireEvent.press(view.getByText("rich.quiz_check"));
    // The verdict is its own line above the explanation, as in ChatGPT.
    expect(view.getByText("rich.quiz_correct")).toBeTruthy();
    expect(view.getByText("Only 6 and 8 are greater than 4.")).toBeTruthy();
  });

  it("shows the exercise pill and the code inside the card", async () => {
    const content = JSON.stringify({
      label: "Exercise 1",
      question: "What will this Python code print?",
      code: "numbers = [2, 4, 6, 8]\nprint(numbers[-1])",
      options: ["2", "8"],
      answer: 1,
      explanation: "`-1` is the last item.",
    });
    const view = await render(<QuizCard content={content} />);
    expect(view.getByText("Exercise 1")).toBeTruthy();
    expect(
      view.getByText("python:numbers = [2, 4, 6, 8]\nprint(numbers[-1])"),
    ).toBeTruthy();
  });

  it("draws code in the explanation as a code block", async () => {
    const content = JSON.stringify({
      question: "What does enumerate give?",
      options: ["Only the values", "Index and value"],
      answer: 1,
      explanation:
        "`enumerate()` gives both.\n\n```python\nfor i, n in enumerate([3, 3]):\n    print(i, n)\n```",
    });
    const view = await render(<QuizCard content={content} />);
    await fireEvent.press(view.getByText("Only the values"));
    await fireEvent.press(view.getByText("rich.quiz_check"));
    expect(view.getByText("rich.quiz_wrong")).toBeTruthy();
    expect(
      view.getByText("python:for i, n in enumerate([3, 3]):\n    print(i, n)"),
    ).toBeTruthy();
  });

  it("says a wrong answer is not quite, and a new pick tries again", async () => {
    const view = await render(
      <QuizCard content={quiz("Wrong-path explanation.")} />,
    );
    await fireEvent.press(view.getByText("[6, 8]"));
    await fireEvent.press(view.getByText("rich.quiz_check"));
    expect(view.getByText("rich.quiz_wrong")).toBeTruthy();
    await fireEvent.press(view.getByText("[12, 16]"));
    expect(view.queryByText("rich.quiz_wrong")).toBeNull();
    expect(view.getByText("rich.quiz_check")).toBeTruthy();
  });

  it("keeps the answer when the card is drawn again", async () => {
    const content = quiz("Remembered explanation.");
    const first = await render(<QuizCard content={content} />);
    await fireEvent.press(first.getByText("[12, 16]"));
    await fireEvent.press(first.getByText("rich.quiz_check"));
    await first.unmount();
    const again = await render(<QuizCard content={content} />);
    expect(again.getByText("rich.quiz_correct")).toBeTruthy();
  });

  it("draws nothing while the question is still streaming in", async () => {
    const view = await render(<QuizCard content='{"question": "What will' />);
    expect(view.toJSON()).toBeNull();
  });

  it("says so instead of drawing a broken question", async () => {
    const view = await render(
      <QuizCard content='{"question": "Pick", "options": ["a"]}' />,
    );
    expect(view.getByText("rich.quiz_error")).toBeTruthy();
  });
});

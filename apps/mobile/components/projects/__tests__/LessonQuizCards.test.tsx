import { fireEvent, render } from "@testing-library/react-native";

import { LessonQuizCards } from "@/components/projects/LessonQuizCards";
import type { QuizChoice } from "@/lib/parseVocabQuiz";

jest.mock("@/lib/haptics", () => ({
  notifySuccess: jest.fn(),
  notifyWarning: jest.fn(),
}));

jest.mock("@/lib/motion", () => ({
  useReduceMotion: () => true,
}));

jest.mock("@/hooks/useResolvedColorScheme", () => ({
  useResolvedColorScheme: () => "light",
}));

const choices: QuizChoice[] = [
  { letter: "A", text: "serendipity" },
  { letter: "B", text: "ephemeral" },
  { letter: "C", text: "ubiquitous" },
  { letter: "D", text: "candid" },
];

describe("LessonQuizCards", () => {
  it("renders lettered choices", async () => {
    const { getByText } = await render(
      <LessonQuizCards choices={choices} onSelect={jest.fn()} />,
    );

    expect(getByText("A")).toBeOnTheScreen();
    expect(getByText("serendipity")).toBeOnTheScreen();
    expect(getByText("ephemeral")).toBeOnTheScreen();
    expect(getByText("ubiquitous")).toBeOnTheScreen();
    expect(getByText("candid")).toBeOnTheScreen();
  });

  it("exposes a disabled accessibility state on every choice", async () => {
    const { getByTestId } = await render(
      <LessonQuizCards choices={choices} disabled onSelect={jest.fn()} />,
    );

    expect(getByTestId("lesson-choice-A").props.accessibilityState).toEqual(
      expect.objectContaining({ disabled: true }),
    );
    expect(getByTestId("lesson-choice-B").props.accessibilityState).toEqual(
      expect.objectContaining({ disabled: true }),
    );
  });

    it("only reports a correct tap to onSelect", async () => {
    const onSelect = jest.fn();
    const onWrongAnswer = jest.fn();
    const { getByTestId } = await render(
      <LessonQuizCards
        choices={choices}
        correctLetter="B"
        onSelect={onSelect}
        onWrongAnswer={onWrongAnswer}
      />,
    );

    fireEvent.press(getByTestId("lesson-choice-A"));
    expect(onSelect).not.toHaveBeenCalled();
    expect(onWrongAnswer).toHaveBeenCalledTimes(1);
    fireEvent.press(getByTestId("lesson-choice-B"));
    expect(onSelect).toHaveBeenCalledWith("B");
  });
});

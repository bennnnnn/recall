import { act, render, fireEvent, waitFor } from "@testing-library/react-native";

import { VocabQuizChoices } from "@/components/VocabQuizChoices";
import type { QuizChoice } from "@/lib/parseVocabQuiz";

jest.mock("expo-haptics", () => ({
  impactAsync: jest.fn(),
  notificationAsync: jest.fn(),
  selectionAsync: jest.fn(),
}));

const choices: QuizChoice[] = [
  { letter: "A", text: "serendipity" },
  { letter: "B", text: "ephemeral" },
  { letter: "C", text: "ubiquitous" },
  { letter: "D", text: "candid" },
];

describe("VocabQuizChoices", () => {
  it("renders all choices", async () => {
    const onSelect = jest.fn();
    const { getByText } = await render(
      <VocabQuizChoices choices={choices} onSelect={onSelect} />,
    );

    expect(getByText("serendipity")).toBeOnTheScreen();
    expect(getByText("ephemeral")).toBeOnTheScreen();
    expect(getByText("ubiquitous")).toBeOnTheScreen();
    expect(getByText("candid")).toBeOnTheScreen();
  });

  it("calls onSelect with the letter when tapped", async () => {
    const onSelect = jest.fn();
    const { getByText } = await render(
      <VocabQuizChoices choices={choices} onSelect={onSelect} />,
    );

    fireEvent.press(getByText("ephemeral"));
    expect(onSelect).toHaveBeenCalledWith("B");
  });

  it("shows correct/wrong state after answering (LANG-UI-010/011)", async () => {
    const onSelect = jest.fn();
    const { getByText } = await render(
      <VocabQuizChoices
        choices={choices}
        correctLetter="A"
        onSelect={onSelect}
      />,
    );

    await fireEvent.press(getByText("ephemeral"));
    expect(onSelect).toHaveBeenCalledWith("B");

    // After answering, the correct answer shows a checkmark and the wrong answer shows a cross
    expect(getByText("✓")).toBeOnTheScreen();
    expect(getByText("✕")).toBeOnTheScreen();
  });

  it("disables chips when disabled prop is true", async () => {
    const onSelect = jest.fn();
    const { getByText } = await render(
      <VocabQuizChoices choices={choices} disabled onSelect={onSelect} />,
    );

    fireEvent.press(getByText("serendipity"));
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("keeps the selected answer busy and unlocks it after submission failure", async () => {
    const onSelect = jest.fn();
    const { getByTestId, getByText, rerender } = await render(
      <VocabQuizChoices
        choices={choices}
        correctLetter="A"
        submitting
        onSelect={onSelect}
      />,
    );

    await fireEvent.press(getByText("ephemeral"));
    expect(getByTestId("quiz-choice-B")).toHaveProp(
      "accessibilityState",
      expect.objectContaining({ selected: true, busy: true }),
    );

    await act(async () => {
      rerender(
        <VocabQuizChoices
          choices={choices}
          correctLetter="A"
          submissionFailed
          onSelect={onSelect}
        />,
      );
    });
    await waitFor(() =>
      expect(getByTestId("quiz-choice-B")).toHaveProp(
        "accessibilityState",
        expect.objectContaining({ selected: false }),
      ),
    );
    fireEvent.press(getByText("ubiquitous"));

    expect(onSelect).toHaveBeenNthCalledWith(2, "C");
  });
});

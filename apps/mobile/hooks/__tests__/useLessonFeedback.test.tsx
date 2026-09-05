import React, { useLayoutEffect } from "react";
import { Text } from "react-native";
import { act, render } from "@testing-library/react-native";
import { useLessonFeedback } from "@/hooks/useLessonFeedback";
import { notifySuccess, notifyWarning } from "@/lib/haptics";
import type { LessonAnswer } from "@/hooks/useLessonSession";

const mockCurrent = () => true;
const mockAudio = { start: jest.fn(), stop: jest.fn() };
jest.mock("@/lib/lessonAudio", () => ({ createLessonAudio: () => mockAudio }));
jest.mock("@/lib/haptics", () => ({ notifySuccess: jest.fn(), notifyWarning: jest.fn() }));

let current: ReturnType<typeof useLessonFeedback>;
function Probe({
  answer,
  effectSound = true,
}: {
  answer: LessonAnswer | null;
  effectSound?: boolean;
}) {
  const value = useLessonFeedback(answer, mockCurrent, effectSound);
  useLayoutEffect(() => {
    current = value;
  });
  return <Text>ok</Text>;
}

function grade(correct: boolean, attemptId: string): LessonAnswer {
  return {
    letter: "A",
    correct,
    attemptId,
    itemId: "one",
    completesWord: correct,
    status: "saved",
  };
}

beforeEach(() => {
  jest.clearAllMocks();
});

it("plays the incorrect cue without speaking feedback copy", async () => {
  const screen = await render(<Probe answer={null} />);
  await act(async () => {
    screen.rerender(<Probe answer={grade(false, "a1")} />);
  });
  expect(notifyWarning).toHaveBeenCalledTimes(1);
  expect(notifySuccess).not.toHaveBeenCalled();
  expect(mockAudio.start).toHaveBeenCalledWith("", "en", false);
});

it("plays the correct cue once per attempt", async () => {
  const screen = await render(<Probe answer={grade(true, "a2")} />);
  expect(notifySuccess).toHaveBeenCalledTimes(1);
  expect(mockAudio.start).toHaveBeenCalledWith("", "en", true);
  await act(async () => {
    screen.rerender(<Probe answer={grade(true, "a2")} />);
  });
  expect(mockAudio.start).toHaveBeenCalledTimes(1);
});

it("still speaks the word when asked", async () => {
  await render(<Probe answer={null} />);
  await act(() => current.speak("hola", "es"));
  expect(mockAudio.start).toHaveBeenCalledWith("hola", "es");
});

it("skips the grade cue when effect sounds are off", async () => {
  await render(<Probe answer={grade(true, "quiet")} effectSound={false} />);
  expect(notifySuccess).toHaveBeenCalledTimes(1);
  expect(mockAudio.start).not.toHaveBeenCalled();
});

it("plays the group-complete woo when asked", async () => {
  await render(<Probe answer={null} />);
  await act(() => current.celebrate());
  expect(mockAudio.start).toHaveBeenCalledWith("", "en", "complete");
});

it("skips the group-complete woo when effect sounds are off", async () => {
  await render(<Probe answer={null} effectSound={false} />);
  await act(() => current.celebrate());
  expect(mockAudio.start).not.toHaveBeenCalled();
});

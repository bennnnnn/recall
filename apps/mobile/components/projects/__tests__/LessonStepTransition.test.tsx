import { Text } from "react-native";
import { render } from "@testing-library/react-native";

import { LessonStepTransition } from "@/components/projects/LessonStepTransition";

jest.mock("@/lib/motion", () => ({
  useReduceMotion: () => true,
  Motion: { duration: { standard: 1 }, easing: { out: undefined, in: undefined } },
}));

it("swaps pane content without dropping the lesson pane", async () => {
  const { getByTestId, getByText, queryByText, rerender } = await render(
    <LessonStepTransition stepKey="one:teach">
      <Text>teach</Text>
    </LessonStepTransition>,
  );
  expect(getByTestId("lesson-pane")).toBeOnTheScreen();
  expect(getByText("teach")).toBeOnTheScreen();

  await rerender(
    <LessonStepTransition stepKey="one:quiz">
      <Text>quiz</Text>
    </LessonStepTransition>,
  );
  expect(getByTestId("lesson-pane")).toBeOnTheScreen();
  expect(getByText("quiz")).toBeOnTheScreen();
  expect(queryByText("teach")).toBeNull();
});

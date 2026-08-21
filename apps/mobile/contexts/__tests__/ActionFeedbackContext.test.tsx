import { act, fireEvent, render } from "@testing-library/react-native";
import { Pressable, Text } from "react-native";

import {
  ActionFeedbackProvider,
  useActionFeedback,
} from "@/contexts/ActionFeedbackContext";
import { notifySuccess } from "@/lib/haptics";

jest.mock("@/components/ActionBanner", () => {
  const { Text: RNText } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    ActionBanner: ({ message, tone }: { message: string; tone: string }) => (
      <RNText>{`${tone}:${message}`}</RNText>
    ),
  };
});
jest.mock("@/lib/haptics", () => ({
  notifySuccess: jest.fn(),
  notifyWarning: jest.fn(),
}));

function Harness() {
  const feedback = useActionFeedback();
  return (
    <Pressable accessibilityRole="button" onPress={() => feedback.success("Saved")}>
      <Text>Trigger</Text>
    </Pressable>
  );
}

describe("ActionFeedbackProvider", () => {
  it("shows centralized success feedback and triggers outcome haptics", async () => {
    const { getByRole, getByText } = await render(
      <ActionFeedbackProvider>
        <Harness />
      </ActionFeedbackProvider>,
    );

    await act(async () => {
      fireEvent.press(getByRole("button"));
    });

    expect(getByText("success:Saved")).toBeOnTheScreen();
    expect(notifySuccess).toHaveBeenCalledTimes(1);
  });
});

import { act, fireEvent, render } from "@testing-library/react-native";
import { Pressable, Text } from "react-native";

import {
  ActionFeedbackProvider,
  useActionFeedback,
} from "@/contexts/ActionFeedbackContext";
import { notifySuccess } from "@/lib/haptics";

jest.mock("@/ui/feedback/ActionBanner", () => {
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

  it("shows the screen's toasts in a provider mounted over it (a full-screen viewer) while it is open", async () => {
    function Viewer() {
      return (
        <ActionFeedbackProvider appearance="media">
          <Text>Viewer</Text>
        </ActionFeedbackProvider>
      );
    }
    function Screen({ viewerOpen }: { viewerOpen: boolean }) {
      const feedback = useActionFeedback();
      return (
        <>
          <Pressable accessibilityRole="button" onPress={() => feedback.error("Could not delete")}>
            <Text>Delete</Text>
          </Pressable>
          {viewerOpen ? <Viewer /> : null}
        </>
      );
    }
    const view = await render(
      <ActionFeedbackProvider>
        <Screen viewerOpen />
      </ActionFeedbackProvider>,
    );
    await act(async () => {
      fireEvent.press(view.getByRole("button"));
    });
    // One toast, drawn by the viewer's provider beside the viewer's content.
    expect(view.getAllByText("error:Could not delete")).toHaveLength(1);
    expect(view.getByText("error:Could not delete").parent).toBe(view.getByText("Viewer").parent);

    await view.rerender(
      <ActionFeedbackProvider>
        <Screen viewerOpen={false} />
      </ActionFeedbackProvider>,
    );
    await act(async () => {
      fireEvent.press(view.getByRole("button"));
    });
    expect(view.getByText("error:Could not delete")).toBeOnTheScreen();
    expect(view.queryByText("Viewer")).toBeNull();
  });
});

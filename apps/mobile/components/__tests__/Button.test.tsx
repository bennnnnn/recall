import { fireEvent, render } from "@testing-library/react-native";

import { Button } from "@/components/Button";

jest.mock("@/components/ActionShimmer", () => {
  const { Text: RNText } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    ActionShimmer: ({ label }: { label: string }) => <RNText>{label}</RNText>,
  };
});

describe("Button", () => {
  it("shows a pending label, blocks duplicate presses, and reports busy", async () => {
    const onPress = jest.fn();
    const { getByRole, getByText } = await render(
      <Button title="Save" loading loadingLabel="Saving…" onPress={onPress} />,
    );

    const button = getByRole("button");
    expect(getByText("Saving…")).toBeOnTheScreen();
    expect(button.props.accessibilityState).toEqual({ disabled: true, busy: true });

    fireEvent.press(button);
    expect(onPress).not.toHaveBeenCalled();
  });

  it("exposes a destructive variant for confirmed dangerous actions", async () => {
    const onPress = jest.fn();
    const { getByRole } = await render(
      <Button title="Delete" variant="destructive" onPress={onPress} />,
    );
    fireEvent.press(getByRole("button"));
    expect(onPress).toHaveBeenCalledTimes(1);
  });
});

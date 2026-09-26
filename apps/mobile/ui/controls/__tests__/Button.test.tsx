import { fireEvent, render } from "@testing-library/react-native";

import { Button } from "../Button";

jest.mock("@/ui/feedback/ActionShimmer", () => {
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

  it("is a pill in three heights", async () => {
    const view = await render(
      <>
        <Button title="Small" size="sm" onPress={jest.fn()} />
        <Button title="Medium" onPress={jest.fn()} />
        <Button title="Large" size="lg" onPress={jest.fn()} />
      </>,
    );
    expect(view.getByRole("button", { name: "Small" })).toHaveStyle({ minHeight: 36, borderRadius: 999 });
    expect(view.getByRole("button", { name: "Medium" })).toHaveStyle({ minHeight: 44 });
    expect(view.getByRole("button", { name: "Large" })).toHaveStyle({ minHeight: 52 });
  });

  it("puts the icon before or after the label", async () => {
    const view = await render(
      <Button title="Get started" icon="arrow-right" iconPlacement="end" onPress={jest.fn()} />,
    );
    const children = view.getByRole("button", { name: "Get started" }).children;
    expect(children).toHaveLength(2);
  });
});

import { fireEvent, render } from "@testing-library/react-native";

import { StepPicker } from "@/components/projects/StepPicker";

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));

jest.mock("@/components/ActionShimmer", () => {
  const { Text, View } = jest.requireActual("react-native");
  return {
    ActionShimmer: ({ label }: { label: string }) => (
      <View testID="action-shimmer">
        <Text>{label}</Text>
      </View>
    ),
  };
});

describe("StepPicker", () => {
  const options = [
    { key: "a", value: "a", label: "Option A" },
    { key: "b", value: "b", label: "Option B" },
  ];

  it("renders label, hint, and every option", async () => {
    const { getByText } = await render(
      <StepPicker
        label="Pick one"
        hint="Choose wisely"
        options={options}
        isSelected={() => false}
        onSelect={jest.fn()}
        backLabel="Back"
        onBack={jest.fn()}
        continueLabel="Continue"
        onContinue={jest.fn()}
      />,
    );

    expect(getByText("Pick one")).toBeOnTheScreen();
    expect(getByText("Choose wisely")).toBeOnTheScreen();
    expect(getByText("Option A")).toBeOnTheScreen();
    expect(getByText("Option B")).toBeOnTheScreen();
    expect(getByText("Back")).toBeOnTheScreen();
    expect(getByText("Continue")).toBeOnTheScreen();
  });

  it("calls onSelect with the pressed option's value (single- or multi-select is the caller's choice)", async () => {
    const onSelect = jest.fn();
    const { getByText } = await render(
      <StepPicker
        label="Pick one"
        hint="Choose wisely"
        options={options}
        isSelected={(v) => v === "a"}
        onSelect={onSelect}
        backLabel="Back"
        onBack={jest.fn()}
        continueLabel="Continue"
        onContinue={jest.fn()}
      />,
    );

    await fireEvent.press(getByText("Option B"));
    expect(onSelect).toHaveBeenCalledWith("b");
  });

  it("calls onBack and onContinue from their respective buttons", async () => {
    const onBack = jest.fn();
    const onContinue = jest.fn();
    const { getByText } = await render(
      <StepPicker
        label="Pick one"
        hint="Choose wisely"
        options={options}
        isSelected={() => false}
        onSelect={jest.fn()}
        backLabel="Back"
        onBack={onBack}
        continueLabel="Continue"
        onContinue={onContinue}
      />,
    );

    await fireEvent.press(getByText("Back"));
    await fireEvent.press(getByText("Continue"));
    expect(onBack).toHaveBeenCalledTimes(1);
    expect(onContinue).toHaveBeenCalledTimes(1);
  });

  it("keeps the create label visible and disables submit while busy", async () => {
    // The daily-goal step's continue button doubles as the final "Create"
    // submit — while creating, it must not be tappable again (double-submit)
    // and must show shared indeterminate feedback without hiding its purpose.
    const onContinue = jest.fn();
    const { getByRole, getByTestId, getByText } = await render(
      <StepPicker
        label="Pick one"
        hint="Choose wisely"
        options={options}
        isSelected={() => false}
        onSelect={jest.fn()}
        backLabel="Back"
        onBack={jest.fn()}
        continueLabel="Create"
        onContinue={onContinue}
        continueBusy
      />,
    );

    const createButton = getByRole("button", { name: "Create" });
    expect(getByText("Create")).toBeOnTheScreen();
    expect(getByTestId("action-shimmer")).toBeOnTheScreen();
    expect(createButton).toHaveProp(
      "accessibilityState",
      expect.objectContaining({ disabled: true, busy: true }),
    );
    fireEvent.press(createButton);
    expect(onContinue).not.toHaveBeenCalled();
  });

  it("shows a checkmark only next to the option isSelected returns true for", async () => {
    const { toJSON } = await render(
      <StepPicker
        label="Pick one"
        hint="Choose wisely"
        options={options}
        isSelected={(v) => v === "b"}
        onSelect={jest.fn()}
        backLabel="Back"
        onBack={jest.fn()}
        continueLabel="Continue"
        onContinue={jest.fn()}
      />,
    );

    const tree = JSON.stringify(toJSON());
    expect((tree.match(/"checkmark"/g) ?? []).length).toBe(1);
  });
});

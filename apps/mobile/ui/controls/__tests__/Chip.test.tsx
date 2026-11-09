import { fireEvent, render } from "@testing-library/react-native";
import { Platform } from "react-native";

import { selection, tap } from "@/lib/haptics";
import { lightTheme } from "@/lib/theme";
import { Chip } from "../Chip";

jest.mock("@/lib/haptics", () => ({ selection: jest.fn(), tap: jest.fn() }));

describe("Chip", () => {
  afterEach(() => {
    jest.restoreAllMocks();
    jest.clearAllMocks();
  });

  it("is a 44 tall choice, and a picked one is checked and indigo", async () => {
    const onPress = jest.fn();
    const view = await render(
      <>
        <Chip accessibilityRole="radio" label="All" selected onPress={jest.fn()} />
        <Chip accessibilityRole="radio" label="Files" onPress={onPress} />
      </>,
    );
    const all = view.getByRole("radio", { name: "All" });
    expect(all.props.accessibilityState).toEqual({ checked: true });
    expect(all).toHaveStyle({ minHeight: 44, backgroundColor: lightTheme.primaryLight, borderColor: lightTheme.primary });
    const files = view.getByRole("radio", { name: "Files" });
    expect(files.props.accessibilityState.checked).toBe(false);
    expect(files).toHaveStyle({ backgroundColor: lightTheme.surface });
    await fireEvent.press(files);
    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it("ticks once when the choice changes, as a segment does, and not for the one already picked", async () => {
    const onPress = jest.fn();
    const view = await render(
      <>
        <Chip accessibilityRole="radio" label="All" selected onPress={onPress} />
        <Chip accessibilityRole="radio" label="Files" onPress={onPress} />
        <Chip accessibilityRole="tab" label="Greek" onPress={onPress} />
      </>,
    );
    await fireEvent.press(view.getByRole("radio", { name: "All" }));
    expect(selection).not.toHaveBeenCalled();
    await fireEvent.press(view.getByRole("radio", { name: "Files" }));
    await fireEvent.press(view.getByRole("button", { name: "Greek" }));
    expect(selection).toHaveBeenCalledTimes(2);
    expect(tap).not.toHaveBeenCalled();
    expect(onPress).toHaveBeenCalledTimes(3);
  });

  // React Native gives VoiceOver nothing for `tab`: the math keyboard's tabs read as bare text.
  it("reads a tab as a button on iOS and a tab on Android, the current one selected", async () => {
    const tabs = () => (
      <>
        <Chip accessibilityRole="tab" label="Basics" selected onPress={jest.fn()} />
        <Chip accessibilityRole="tab" label="Greek" onPress={jest.fn()} />
      </>
    );
    const ios = await render(tabs());
    expect(ios.getByRole("button", { name: "Basics" }).props.accessibilityState).toEqual({ selected: true });
    expect(ios.getByRole("button", { name: "Greek" }).props.accessibilityState.selected).toBe(false);
    await ios.unmount();

    jest.replaceProperty(Platform, "OS", "android");
    const android = await render(tabs());
    expect(android.getByRole("tab", { name: "Basics" }).props.accessibilityState.selected).toBe(true);
  });
});

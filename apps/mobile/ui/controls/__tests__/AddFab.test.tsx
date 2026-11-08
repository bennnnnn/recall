import { Keyboard, Platform, StyleSheet, type KeyboardEvent } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { act, render } from "@testing-library/react-native";

import { AddFab } from "../AddFab";
import { fabBottom } from "../addFabLayout";

jest.mock("@/lib/haptics", () => ({ tap: jest.fn() }));

/** The navigation bar (Android) or home indicator (iOS) the safe area reports. */
const BAR = 48;
const KEYBOARD = 300;
type Listener = (event: KeyboardEvent) => void;
const listeners = new Map<string, Listener>();

const keyboard = (name: string, height: number) =>
  act(async () => {
    listeners.get(name)?.({ endCoordinates: { height, screenX: 0, screenY: 0, width: 0 } } as KeyboardEvent);
  });

async function slotBottom() {
  const view = await render(<AddFab onPress={jest.fn()} accessibilityLabel="Add" />);
  return () => StyleSheet.flatten(view.getByTestId("add-fab-slot").props.style).bottom;
}

describe("AddFab", () => {
  beforeEach(() => {
    jest.mocked(useSafeAreaInsets).mockReturnValue({ top: 0, left: 0, right: 0, bottom: BAR });
    listeners.clear();
    jest.spyOn(Keyboard, "addListener").mockImplementation(((name: string, listener: Listener) => {
      listeners.set(name, listener);
      return { remove: jest.fn() };
    }) as never);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("on Android rides the keyboard, whose height already counts the navigation bar", async () => {
    jest.replaceProperty(Platform, "OS", "android");
    const bottom = await slotBottom();
    expect(bottom()).toBe(fabBottom(BAR));

    // React Native reports the keyboard above the bar; the hook adds the bar back once.
    await keyboard("keyboardDidShow", KEYBOARD - BAR);
    expect(bottom()).toBe(fabBottom(0) + KEYBOARD);
  });

  it("on iOS keeps the lift it had", async () => {
    jest.replaceProperty(Platform, "OS", "ios");
    const bottom = await slotBottom();
    await keyboard("keyboardWillShow", KEYBOARD);

    expect(bottom()).toBe(fabBottom(BAR) + KEYBOARD);
  });
});

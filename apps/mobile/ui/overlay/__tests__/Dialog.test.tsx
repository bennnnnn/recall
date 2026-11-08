import { Keyboard, Platform, StyleSheet, type KeyboardEvent } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { act, render } from "@testing-library/react-native";

import { Space } from "@/lib/space";
import { lightTheme as mockLightTheme } from "@/lib/theme";

import { Dialog } from "../Dialog";

jest.mock("@/lib/theme", () => ({
  ...jest.requireActual("@/lib/theme"),
  useTheme: () => mockLightTheme,
}));

const NAV_BAR = 48;
type Listener = (event: KeyboardEvent) => void;
const listeners = new Map<string, Listener>();

describe("Dialog with a text field", () => {
  beforeEach(() => {
    jest.mocked(useSafeAreaInsets).mockReturnValue({ top: 0, left: 0, right: 0, bottom: NAV_BAR });
    listeners.clear();
    jest.spyOn(Keyboard, "addListener").mockImplementation(((name: string, listener: Listener) => {
      listeners.set(name, listener);
      return { remove: jest.fn() };
    }) as never);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("on Android lifts the card by the keyboard and the navigation bar it is measured above", async () => {
    jest.replaceProperty(Platform, "OS", "android");
    const view = await render(<Dialog visible avoidKeyboard title="Time" onClose={jest.fn()} />);
    const paddingBottom = () => StyleSheet.flatten(view.getByTestId("app-dialog-frame").props.style).paddingBottom;
    expect(paddingBottom()).toBe(Space.lg);

    await act(async () => {
      listeners.get("keyboardDidShow")?.({
        endCoordinates: { height: 252, screenX: 0, screenY: 0, width: 0 },
      } as KeyboardEvent);
    });
    expect(paddingBottom()).toBe(Space.lg + 252 + NAV_BAR);
  });
});

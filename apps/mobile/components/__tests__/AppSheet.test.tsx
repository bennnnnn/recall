import { act, fireEvent, render } from "@testing-library/react-native";
import { Keyboard, Platform, Text, type EmitterSubscription, type KeyboardEvent } from "react-native";

import { AppSheet } from "@/components/AppSheet";

jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 34, left: 0, right: 0 }),
}));

describe("AppSheet", () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("renders its children when visible", async () => {
    const { getByText } = await render(
      <AppSheet visible onClose={jest.fn()}>
        <Text>sheet body</Text>
      </AppSheet>,
    );

    expect(getByText("sheet body")).toBeOnTheScreen();
  });

  it("calls onClose when the scrim is pressed (backdropDismiss default true)", async () => {
    const onClose = jest.fn();
    const { getByTestId } = await render(
      <AppSheet visible onClose={onClose}>
        <Text>body</Text>
      </AppSheet>,
    );

    await fireEvent.press(getByTestId("app-sheet-backdrop"));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does not dismiss on scrim press when backdropDismiss is false", async () => {
    const onClose = jest.fn();
    const { getByTestId } = await render(
      <AppSheet visible onClose={onClose} backdropDismiss={false}>
        <Text>body</Text>
      </AppSheet>,
    );

    await fireEvent.press(getByTestId("app-sheet-backdrop"));

    expect(onClose).not.toHaveBeenCalled();
  });

  it("renders the grabber handle for the bottom variant by default", async () => {
    const { queryByTestId } = await render(
      <AppSheet visible onClose={jest.fn()}>
        <Text>body</Text>
      </AppSheet>,
    );

    expect(queryByTestId("app-sheet-handle")).not.toBeNull();
  });

  it("omits the handle for the center variant", async () => {
    const { queryByTestId } = await render(
      <AppSheet visible onClose={jest.fn()} variant="center">
        <Text>body</Text>
      </AppSheet>,
    );

    expect(queryByTestId("app-sheet-handle")).toBeNull();
  });

  it("omits the handle when withHandle is false", async () => {
    const { queryByTestId } = await render(
      <AppSheet visible onClose={jest.fn()} withHandle={false}>
        <Text>body</Text>
      </AppSheet>,
    );

    expect(queryByTestId("app-sheet-handle")).toBeNull();
  });

  it("BUG FIX regression: lifts the bottom sheet above the keyboard (Android Modal)", async () => {
    const showEvent = Platform.OS === "ios" ? "keyboardWillShow" : "keyboardDidShow";
    let showHandler: ((e: KeyboardEvent) => void) | undefined;
    jest.spyOn(Keyboard, "addListener").mockImplementation((event, handler) => {
      if (event === showEvent) {
        showHandler = handler as (e: KeyboardEvent) => void;
      }
      return { remove: jest.fn() } as EmitterSubscription;
    });

    const { getByTestId } = await render(
      <AppSheet visible onClose={jest.fn()} keyboardAvoiding>
        <Text>new list</Text>
      </AppSheet>,
    );

    expect(getByTestId("app-sheet-keyboard-host")).toHaveStyle({ paddingBottom: 0 });

    await act(async () => {
      showHandler?.({
        endCoordinates: { height: 320, screenX: 0, screenY: 0, width: 0 },
      } as KeyboardEvent);
    });

    expect(getByTestId("app-sheet-keyboard-host")).toHaveStyle({ paddingBottom: 320 });
  });
});

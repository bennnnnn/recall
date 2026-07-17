import { fireEvent, render } from "@testing-library/react-native";
import { Text } from "react-native";

import { AppSheet } from "@/components/AppSheet";

jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));

describe("AppSheet", () => {
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

  it("renders floating sheets with a handle still visible", async () => {
    const { getByText, queryByTestId } = await render(
      <AppSheet visible onClose={jest.fn()} floating>
        <Text>floating body</Text>
      </AppSheet>,
    );

    expect(getByText("floating body")).toBeOnTheScreen();
    expect(queryByTestId("app-sheet-handle")).not.toBeNull();
  });
});

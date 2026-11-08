import { act, render } from "@testing-library/react-native";

import { fakeAndroidBack } from "@/components/__tests__/support/androidBack";

import { AndroidBackScreen, useAndroidBack } from "../useAndroidBack";

function Mode({ open, onBack }: { open: boolean; onBack: () => void }) {
  useAndroidBack(open, onBack);
  return null;
}

afterEach(() => {
  jest.restoreAllMocks();
});

describe("useAndroidBack", () => {
  it("closes what is open and goes no further; with nothing open Back leaves the screen", async () => {
    const back = fakeAndroidBack();
    const close = jest.fn();
    const view = await render(<Mode open onBack={close} />);

    expect(back.press()).toBe(true);
    expect(close).toHaveBeenCalledTimes(1);

    await view.rerender(<Mode open={false} onBack={close} />);
    expect(back.press()).toBe(false);
    expect(close).toHaveBeenCalledTimes(1);
  });

  it("closes the last one opened first, even after the first one's callback changed", async () => {
    const back = fakeAndroidBack();
    const closePad = jest.fn();
    const closeSheet = jest.fn();
    const tree = (sheetOpen: boolean, padClose: () => void) => (
      <>
        <Mode open onBack={padClose} />
        <Mode open={sheetOpen} onBack={closeSheet} />
      </>
    );
    const view = await render(tree(false, closePad));
    await view.rerender(tree(true, closePad));
    // A new callback for the pad does not put it back on top of the sheet.
    const closePadLater = jest.fn();
    await view.rerender(tree(true, closePadLater));

    await act(() => {
      back.press();
    });
    expect(closeSheet).toHaveBeenCalledTimes(1);
    expect(closePadLater).not.toHaveBeenCalled();

    await view.rerender(tree(false, closePadLater));
    back.press();
    expect(closePadLater).toHaveBeenCalledTimes(1);
    expect(closePad).not.toHaveBeenCalled();
  });

  it("lets Back go to the screen pushed over the one that left something open", async () => {
    const back = fakeAndroidBack();
    const close = jest.fn();
    let onTop = true;
    await render(
      <AndroidBackScreen isOnTop={() => onTop}>
        <Mode open onBack={close} />
      </AndroidBackScreen>,
    );

    onTop = false;
    expect(back.press()).toBe(false);
    expect(close).not.toHaveBeenCalled();

    onTop = true;
    expect(back.press()).toBe(true);
    expect(close).toHaveBeenCalledTimes(1);
  });
});

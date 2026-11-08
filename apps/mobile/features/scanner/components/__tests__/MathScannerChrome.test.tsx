import { act, fireEvent, render } from "@testing-library/react-native";
import { StyleSheet, type LayoutChangeEvent } from "react-native";

import { MathScannerChrome } from "@/features/scanner/components/MathScannerChrome";
import {
  SCANNER_SHUTTER_PX,
  SCANNER_SUBJECT_SWITCHER_PX,
  SCANNER_SUBJECT_TAB_PX,
} from "@/lib/math/scannerRegion";
import { Space } from "@/lib/space";

const INSETS = { top: 47, bottom: 34, left: 0, right: 0 };
/** The chrome's own bottom padding: the safe area, then a little air. */
const BOTTOM_PAD = Math.max(INSETS.bottom, Space.md) + Space.sm;
/** The camera's controls as drawn at the default text size: the shutter row, its gap, the tabs. */
const CONTROLS_AT_DEFAULT_SIZE = BOTTOM_PAD + SCANNER_SHUTTER_PX + Space.sm + SCANNER_SUBJECT_SWITCHER_PX;

function chrome(error: string | null) {
  return (
    <MathScannerChrome
      insets={INSETS}
      granted
      preview={false}
      busy={false}
      torchOn={false}
      subject="math"
      error={error}
      onClose={jest.fn()}
      onSubjectChange={jest.fn()}
      onToggleTorch={jest.fn()}
      onOpenPhotos={jest.fn()}
      onOpenFiles={jest.fn()}
      onCapture={jest.fn()}
      onRetake={jest.fn()}
      onSolve={jest.fn()}
    />
  );
}

const layout = (height: number) =>
  ({ nativeEvent: { layout: { x: 0, y: 0, width: 390, height } } }) as LayoutChangeEvent;

describe("MathScannerChrome", () => {
  it("draws the subject tabs' row at the height the crop frame and the banner count on", async () => {
    const view = await render(chrome(null));
    const tab = view.getByTestId("scanner-subject-math");
    const { top, bottom } = tab.props.hitSlop as { top: number; bottom: number };
    expect(StyleSheet.flatten(tab.props.style).minHeight).toBe(SCANNER_SUBJECT_TAB_PX);
    // The row pads the pill by its hitSlop, so the row is the 44 pt target.
    expect(SCANNER_SUBJECT_TAB_PX + top + bottom).toBe(SCANNER_SUBJECT_SWITCHER_PX);
    expect(SCANNER_SUBJECT_SWITCHER_PX).toBe(Space.minTouch);
  });

  it("keeps the error banner above the subject tabs when a large text size makes them taller", async () => {
    const view = await render(chrome("chat.math_scan_failed"));
    const bannerBottom = () => StyleSheet.flatten(view.getByTestId("math-scanner-error").props.style).bottom;
    const atDefaultSize = BOTTOM_PAD + SCANNER_SHUTTER_PX + SCANNER_SUBJECT_SWITCHER_PX + Space.xl;
    expect(bannerBottom()).toBe(atDefaultSize);

    // Measured at the default size, the controls end below the banner: it stays put.
    await act(async () => {
      fireEvent(view.getByTestId("math-scanner-controls"), "layout", layout(CONTROLS_AT_DEFAULT_SIZE));
    });
    expect(bannerBottom()).toBe(atDefaultSize);
    expect(bannerBottom()).toBeGreaterThan(CONTROLS_AT_DEFAULT_SIZE);

    // Tabs twice as tall at a large text size: the banner rises with them and stays clear.
    const tall = CONTROLS_AT_DEFAULT_SIZE + SCANNER_SUBJECT_SWITCHER_PX;
    await act(async () => {
      fireEvent(view.getByTestId("math-scanner-controls"), "layout", layout(tall));
    });
    expect(bannerBottom()).toBe(tall + Space.sm);
  });
});

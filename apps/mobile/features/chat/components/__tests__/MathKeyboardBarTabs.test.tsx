import { fireEvent, render } from "@testing-library/react-native";

import { MathKeyboardBar } from "@/features/chat/components/MathKeyboardBar";

const noop = () => {};

function renderPad() {
  return render(
    <MathKeyboardBar
      open
      height={260}
      onToggle={noop}
      onInsert={noop}
      onCaret={noop}
      onAsk={noop}
      onStop={noop}
      streaming={false}
      onBackspace={noop}
      onPaste={noop}
      group="basics"
      onGroupChange={noop}
    />,
  );
}

// "Greek" and "Converter" sat cut off against the pinned Paste and ABC buttons, with no
// sign the row went on.
describe("math keyboard tab row", () => {
  it("fades its cut edge while tabs run on past Paste and ABC", async () => {
    const view = await renderPad();
    const tabs = view.getByTestId("math-keyboard-tabs");
    expect(view.queryByTestId("scroll-fade-end")).toBeNull();
    await fireEvent(tabs, "layout", { nativeEvent: { layout: { width: 220, height: 36 } } });
    await fireEvent(tabs, "contentSizeChange", 480, 36);
    expect(view.getByTestId("scroll-fade-end")).toBeTruthy();
    // Scrolled to the end, nothing is cut on the right: the left edge fades instead.
    await fireEvent.scroll(tabs, { nativeEvent: { contentOffset: { x: 260, y: 0 } } });
    expect(view.queryByTestId("scroll-fade-end")).toBeNull();
    expect(view.getByTestId("scroll-fade-start")).toBeTruthy();
  });

  it("draws no fade when every tab fits", async () => {
    const view = await renderPad();
    const tabs = view.getByTestId("math-keyboard-tabs");
    await fireEvent(tabs, "layout", { nativeEvent: { layout: { width: 480, height: 36 } } });
    await fireEvent(tabs, "contentSizeChange", 400, 36);
    expect(view.queryByTestId("scroll-fade-end")).toBeNull();
    expect(view.queryByTestId("scroll-fade-start")).toBeNull();
  });
});

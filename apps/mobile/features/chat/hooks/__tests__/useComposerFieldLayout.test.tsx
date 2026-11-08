import type { LayoutChangeEvent } from "react-native";
import { act, renderHook } from "@testing-library/react-native";

import { fakeAndroidBack } from "@/components/__tests__/support/androidBack";
import { useComposerFieldLayout } from "@/features/chat/hooks/useComposerFieldLayout";

const fieldLayout = (width: number) =>
  ({ nativeEvent: { layout: { x: 0, y: 0, width, height: 24 } } }) as LayoutChangeEvent;

const DRAFT = "Plan a weekend in Lisbon";

describe("useComposerFieldLayout", () => {
  it("does not render for a measure that changes neither the line count nor the field", async () => {
    let renders = 0;
    const { result } = await renderHook(() => {
      renders += 1;
      return useComposerFieldLayout({ input: DRAFT, draftRevision: 0, fontScale: 1 });
    });
    await act(() => result.current.onInputLayout(fieldLayout(280)));
    await act(() => result.current.onTextMeasure({ height: 24 }));
    const measured = renders;

    // The next letter stays on the same line.
    await act(() => result.current.onTextMeasure({ height: 24 }));
    expect(renders).toBe(measured);

    // Another line does change the field.
    await act(() => result.current.onTextMeasure({ height: 48 }));
    expect(renders).toBe(measured + 1);
    expect(result.current.fieldHeight).toBe(60);
  });

  it("reports the extra height a Return line adds, for the thread to clear", async () => {
    const onInputFrameExtraChange = jest.fn();
    await renderHook(() =>
      useComposerFieldLayout({
        input: "First line\nSecond line",
        draftRevision: 0,
        fontScale: 1,
        onInputFrameExtraChange,
      }),
    );
    // One Return adds a line; the one row is in COMPOSER_HEIGHT.
    expect(onInputFrameExtraChange).toHaveBeenLastCalledWith(24);
  });

  it("moves the thread by the button row too when a Return drops the buttons under the field", async () => {
    const onInputFrameExtraChange = jest.fn();
    await renderHook(() =>
      useComposerFieldLayout({
        input: "First line\nSecond line",
        draftRevision: 0,
        fontScale: 1,
        buttonRowBelow: true,
        onInputFrameExtraChange,
      }),
    );
    expect(onInputFrameExtraChange).toHaveBeenLastCalledWith(24 + 36);
  });

  it("reports nothing extra for one line, so an empty composer adds no padding of its own", async () => {
    const onInputFrameExtraChange = jest.fn();
    await renderHook(() =>
      useComposerFieldLayout({ input: "", draftRevision: 0, fontScale: 1, onInputFrameExtraChange }),
    );
    expect(onInputFrameExtraChange).toHaveBeenLastCalledWith(0);
  });

  it("folds the full-height editor on Android Back, and lets the next Back leave the chat", async () => {
    const back = fakeAndroidBack();
    const { result } = await renderHook(() =>
      useComposerFieldLayout({ input: DRAFT, draftRevision: 0, fontScale: 1 }),
    );
    await act(() => result.current.toggleExpanded());
    expect(result.current.composerExpanded).toBe(true);

    let handled = false;
    await act(() => {
      handled = back.press();
    });

    expect(handled).toBe(true);
    expect(result.current.composerExpanded).toBe(false);
    expect(back.press()).toBe(false);
    jest.restoreAllMocks();
  });
});

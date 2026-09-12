import { act, renderHook } from "@testing-library/react-native";
import { useState } from "react";

import { useMathKeyboardInsert } from "@/hooks/useMathKeyboardInsert";
import { clipboardIsImageOnly } from "@/lib/math/mathClipboard";

jest.mock("@/lib/math/mathClipboard", () => ({
  clipboardIsImageOnly: jest.fn(async () => false),
}));

function useHarness(initial = "", onImageOnlyPaste?: () => void) {
  const [input, setInput] = useState(initial);
  const math = useMathKeyboardInsert({ input, setInput, onImageOnlyPaste });
  return { input, math };
}

describe("useMathKeyboardInsert", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("normalizes an explicit math-bar paste", async () => {
    const { result } = await renderHook(() => useHarness());
    await act(async () => {
      await result.current.math.pasteText("2 × 3");
    });
    expect(result.current.input).toBe("$2 \\times 3$");
  });

  it.each([
    "What is sqrt{81}?",
    "Let x=-5. Evaluate x^2",
    "graph y<2x",
    "The price is $5.00",
    "Use $x^2$ in this formula",
  ])("preserves every native typing step in %s", async (text) => {
    const { result } = await renderHook(() => useHarness());
    for (let i = 1; i <= text.length; i += 1) {
      const next = text.slice(0, i);
      await act(() => result.current.math.onChangeText(next));
      expect(result.current.input).toBe(next);
      expect(result.current.math.forcedSelection).toBeUndefined();
    }
  });

  it("trusts native replacements even when the last selection event is stale", async () => {
    const { result } = await renderHook(() => useHarness("Let x=-5. Evaluate x^2"));
    await act(() => result.current.math.moveCaret(21));
    await act(() => result.current.math.onChangeText("Let x=-6. Evaluate x^2"));
    expect(result.current.input).toBe("Let x=-6. Evaluate x^2");
    expect(result.current.math.forcedSelection).toBeUndefined();
  });

  it("preserves coalesced native math input without treating it as a paste", async () => {
    const { result } = await renderHook(() => useHarness());
    await act(() => {
      result.current.math.onChangeText("Let x=-5. Evaluate ");
      result.current.math.onChangeText("Let x=-5. Evaluate x^");
      result.current.math.onChangeText("Let x=-5. Evaluate x^2");
    });
    expect(result.current.input).toBe("Let x=-5. Evaluate x^2");
  });

  it("normalizes math-bar paste even when replacing a longer selection", async () => {
    const { result } = await renderHook(() => useHarness("abcdefgh"));
    await act(() => {
      result.current.math.onSelectionChange({
        nativeEvent: { selection: { start: 0, end: 8 } },
      } as Parameters<typeof result.current.math.onSelectionChange>[0]);
    });
    await act(async () => {
      await result.current.math.pasteText("2 × 3");
    });
    expect(result.current.input).toBe("$2 \\times 3$");
  });

  it("resets math editing for another owner even when the draft text is identical", async () => {
    const { result, rerender } = await renderHook(
      ({ draftRevision }) => useMathKeyboardInsert({ input: "$x^2$", setInput: jest.fn(), draftRevision }),
      { initialProps: { draftRevision: 1 } },
    );
    await act(() => result.current.toggleMathBar());
    expect(result.current.showMathPreview).toBe(true);
    await rerender({ draftRevision: 2 });
    expect(result.current.showMathPreview).toBe(false);
    expect(result.current.mathBarOpen).toBe(false);
    expect(result.current.forcedSelection).toBeUndefined();
  });

  it("pins the caret after the last formula when the bar closes", async () => {
    const { result } = await renderHook(() => useHarness("solve $x^2+1$"));
    await act(() => {
      result.current.math.toggleMathBar();
    });
    await act(() => {
      result.current.math.toggleMathBar();
    });
    const n = "solve $x^2+1$".length;
    expect(result.current.math.selection).toEqual({ start: n, end: n });
    expect(result.current.math.selection.start).not.toBe(0);
  });

  it("does not probe the clipboard for ordinary typing", async () => {
    const { result } = await renderHook(() => useHarness("", jest.fn()));
    await act(() => {
      result.current.math.onChangeText("because");
    });
    expect(clipboardIsImageOnly).not.toHaveBeenCalled();
  });

  it("probes the clipboard for a math-glyph paste", async () => {
    const { result } = await renderHook(() => useHarness("", jest.fn()));
    await act(() => {
      result.current.math.onChangeText("√16+x=20");
    });
    expect(clipboardIsImageOnly).toHaveBeenCalled();
  });
});

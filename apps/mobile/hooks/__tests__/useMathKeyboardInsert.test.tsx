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

  it("rewrites math-bar paste the same way as typing", async () => {
    const { result } = await renderHook(() => useHarness());
    await act(async () => {
      await result.current.math.pasteText("2 × 3");
    });
    expect(result.current.input).toBe("$2 \\times 3$");
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

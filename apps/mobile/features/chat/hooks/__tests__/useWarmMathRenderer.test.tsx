import { act, renderHook } from "@testing-library/react-native";

import { useWarmMathRenderer, WARM_MATH_AFTER_MS } from "@/features/chat/hooks/useWarmMathRenderer";
import { warmSvgMath } from "@/lib/math/svgMath";

jest.mock("@/lib/math/svgMath", () => ({ warmSvgMath: jest.fn() }));

beforeEach(() => {
  jest.useFakeTimers();
  jest.mocked(warmSvgMath).mockClear();
});
afterEach(() => jest.useRealTimers());

describe("useWarmMathRenderer", () => {
  it("loads the maths renderer once the chat has settled and gone idle", async () => {
    await renderHook(() => useWarmMathRenderer());
    await act(async () => {
      jest.advanceTimersByTime(WARM_MATH_AFTER_MS - 1);
    });
    expect(warmSvgMath).not.toHaveBeenCalled();
    await act(async () => {
      jest.advanceTimersByTime(100);
    });
    expect(warmSvgMath).toHaveBeenCalledTimes(1);
  });

  it("does nothing for a chat that closes first", async () => {
    const { unmount } = await renderHook(() => useWarmMathRenderer());
    await unmount();
    await act(async () => {
      jest.advanceTimersByTime(WARM_MATH_AFTER_MS + 1_000);
    });
    expect(warmSvgMath).not.toHaveBeenCalled();
  });
});

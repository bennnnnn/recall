import { act, renderHook } from "@testing-library/react-native";

import { useScannerFocus } from "@/features/scanner/hooks/useScannerFocus";

function camera() {
  const focusAt = jest.fn();
  return { ref: { current: { takePictureAsync: jest.fn(), focusAt } }, focusAt };
}

it("focuses the live camera where the student tapped, and rings the spot", async () => {
  const { ref, focusAt } = camera();
  const { result } = await renderHook(() => useScannerFocus(ref, true));
  await act(async () => result.current.focusAt({ x: 120, y: 300 }));
  expect(focusAt).toHaveBeenCalledWith({ x: 120, y: 300 });
  expect(result.current.focusPoint).toEqual({ x: 120, y: 300, id: 1 });
  // A second tap on the same spot starts the ring again.
  await act(async () => result.current.focusAt({ x: 120, y: 300 }));
  expect(result.current.focusPoint?.id).toBe(2);
});

it("does nothing on a still, or before the camera runs, and shows no ring", async () => {
  const { ref, focusAt } = camera();
  const { result } = await renderHook(() => useScannerFocus(ref, false));
  await act(async () => result.current.focusAt({ x: 120, y: 300 }));
  expect(focusAt).not.toHaveBeenCalled();
  expect(result.current.focusPoint).toBeNull();
});

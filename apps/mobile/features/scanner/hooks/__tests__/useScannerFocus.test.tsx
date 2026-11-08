import { act, render, renderHook } from "@testing-library/react-native";

import { ScannerFocusRing } from "@/features/scanner/components/ScannerFocusRing";

import { useScannerFocus } from "@/features/scanner/hooks/useScannerFocus";

function camera() {
  const focusAt = jest.fn();
  return { ref: { current: { takePictureAsync: jest.fn(), focusAt } }, focusAt };
}

it("focuses the live camera where the student tapped, and rings the spot", async () => {
  const { ref, focusAt } = camera();
  const { result } = await renderHook(() => useScannerFocus(ref, true, 100));
  await act(async () => result.current.focusAt({ x: 120, y: 300 }));
  expect(focusAt).toHaveBeenCalledWith({ x: 120, y: 300 });
  expect(result.current.focusPoint).toEqual({ x: 120, y: 300, id: 1 });
  // A second tap on the same spot starts the ring again.
  await act(async () => result.current.focusAt({ x: 120, y: 300 }));
  expect(result.current.focusPoint?.id).toBe(2);
});

it("does nothing on a still, or before the camera runs, and shows no ring", async () => {
  const { ref, focusAt } = camera();
  const { result } = await renderHook(() => useScannerFocus(ref, false, 100));
  await act(async () => result.current.focusAt({ x: 120, y: 300 }));
  expect(focusAt).not.toHaveBeenCalled();
  expect(result.current.focusPoint).toBeNull();
});

it("rings only for a new tap, not for an old point shown again after a retake", async () => {
  const reanimated = jest.requireMock<typeof import("react-native-reanimated")>("react-native-reanimated");
  const fade = jest.spyOn(reanimated, "withDelay");
  const tapped = { x: 120, y: 300, id: 1 };
  const view = await render(<ScannerFocusRing point={tapped} />);
  expect(fade).toHaveBeenCalledTimes(1);
  // The still comes up (no point), then the camera again with the same last tap.
  await view.rerender(<ScannerFocusRing point={null} />);
  await view.rerender(<ScannerFocusRing point={tapped} />);
  expect(fade).toHaveBeenCalledTimes(1);
  await view.rerender(<ScannerFocusRing point={{ ...tapped, id: 2 }} />);
  expect(fade).toHaveBeenCalledTimes(2);
  fade.mockRestore();
});

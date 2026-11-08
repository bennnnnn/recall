import { type RefObject, useCallback, useMemo, useState } from "react";
import { Gesture } from "react-native-gesture-handler";

import type { LiveScannerCameraHandle } from "@/features/scanner/components/LiveMathScannerCamera";
import type { FocusPoint } from "@/features/scanner/components/ScannerFocusRing";

/**
 * Tap to focus: a tap on the live viewfinder, inside the frame or outside it, focuses the
 * camera there and shows a ring while it does. `live` is a running camera with no still up.
 */
export function useScannerFocus(cameraRef: RefObject<LiveScannerCameraHandle | null>, live: boolean) {
  const [focusPoint, setFocusPoint] = useState<FocusPoint | null>(null);
  const focusAt = useCallback((point: { x: number; y: number }) => {
    if (!live) return;
    cameraRef.current?.focusAt(point);
    setFocusPoint((last) => ({ ...point, id: (last?.id ?? 0) + 1 }));
  }, [cameraRef, live]);
  // Outside the frame: the frame's own gesture reports taps inside it (`onTap`).
  const tapGesture = useMemo(
    () => Gesture.Tap().runOnJS(true).onEnd((event) => focusAt({ x: event.x, y: event.y })),
    [focusAt],
  );
  return { focusPoint: live ? focusPoint : null, focusAt, tapGesture };
}

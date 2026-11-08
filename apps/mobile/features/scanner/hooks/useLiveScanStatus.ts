import { useCallback, useRef, useState } from "react";

import type { LiveScannerDetection } from "@/features/scanner/components/LiveMathScannerCamera";
import type { LiveScanFrameStatus } from "@/features/scanner/components/MathScannerCropOverlay";
import { selection } from "@/lib/haptics";

/**
 * What the live frame shows of the camera's reading: nothing, text found, or text held
 * steady (a tick of haptics the moment it is). Moving the frame or the subject starts over;
 * `readEpoch` counts the restarts, so the camera's reader starts over with the status.
 */
export function useLiveScanStatus() {
  const [liveStatus, setLiveStatus] = useState<LiveScanFrameStatus>("idle");
  const [readEpoch, setReadEpoch] = useState(0);
  const liveReadyRef = useRef(false);
  const resetLive = useCallback(() => {
    setLiveStatus("idle");
    setReadEpoch((epoch) => epoch + 1);
    liveReadyRef.current = false;
  }, []);
  const handleLiveDetection = useCallback((detection: LiveScannerDetection) => {
    setLiveStatus(detection.stable ? "ready" : detection.hasText ? "detecting" : "idle");
    if (detection.stable && !liveReadyRef.current) selection();
    liveReadyRef.current = detection.stable;
  }, []);
  return { liveStatus, readEpoch, resetLive, handleLiveDetection };
}

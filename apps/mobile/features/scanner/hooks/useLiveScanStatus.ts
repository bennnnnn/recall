import { useCallback, useRef, useState } from "react";

import type { LiveScannerDetection } from "@/features/scanner/components/LiveMathScannerCamera";
import type { LiveScanFrameStatus } from "@/features/scanner/components/MathScannerCropOverlay";
import { selection } from "@/lib/haptics";

/**
 * What the live frame shows of the camera's reading: nothing, text found, or text held
 * steady (a tick of haptics the moment it is). Moving the frame or the subject starts over.
 */
export function useLiveScanStatus() {
  const [liveStatus, setLiveStatus] = useState<LiveScanFrameStatus>("idle");
  const liveReadyRef = useRef(false);
  const resetLive = useCallback(() => {
    setLiveStatus("idle");
    liveReadyRef.current = false;
  }, []);
  const handleLiveDetection = useCallback((detection: LiveScannerDetection) => {
    setLiveStatus(detection.stable ? "ready" : detection.hasText ? "detecting" : "idle");
    if (detection.stable && !liveReadyRef.current) selection();
    liveReadyRef.current = detection.stable;
  }, []);
  return { liveStatus, resetLive, handleLiveDetection };
}

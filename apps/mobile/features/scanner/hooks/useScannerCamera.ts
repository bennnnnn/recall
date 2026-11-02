import { useCallback, useEffect, useRef, useState } from "react";

import type { LiveScannerCameraHandle } from "@/features/scanner/components/LiveMathScannerCamera";
import {
  CAMERA_READY,
  CAMERA_STARTING,
  CAMERA_START_TIMEOUT_MS,
  cameraUnavailable,
  statusOnOpen,
  type ScannerCameraStatus,
} from "@/features/scanner/model/cameraStatus";

type Args = {
  /** The live camera is mounted and asked to run (permission, scanner open, no still photo). */
  live: boolean;
};

/**
 * The live camera's status for the scanner: starting, ready, or unavailable with a reason.
 * A camera that gives no ready signal within `CAMERA_START_TIMEOUT_MS` of being asked to run
 * is unavailable; a ready signal that comes later still makes it ready.
 */
export function useScannerCamera({ live }: Args) {
  const cameraRef = useRef<LiveScannerCameraHandle>(null);
  const [status, setStatus] = useState<ScannerCameraStatus>(CAMERA_STARTING);
  const starting = status.kind === "starting";

  useEffect(() => {
    if (!starting || !live) return;
    const timer = setTimeout(() => setStatus(cameraUnavailable("timeout")), CAMERA_START_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, [live, starting]);

  /** A newly opened scanner waits for the camera again. */
  const resetCamera = useCallback(() => setStatus(statusOnOpen), []);
  const onReady = useCallback(() => setStatus(CAMERA_READY), []);
  const onError = useCallback(() => setStatus(cameraUnavailable("failed")), []);
  const onUnavailable = useCallback(() => setStatus(cameraUnavailable("missing")), []);

  return { cameraRef, status, resetCamera, onReady, onError, onUnavailable };
}

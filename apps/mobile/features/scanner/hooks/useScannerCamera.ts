import { useCallback, useEffect, useRef, useState } from "react";

import type { LiveScannerCameraHandle } from "@/features/scanner/components/LiveMathScannerCamera";
import {
  CAMERA_ERROR_GRACE_MS,
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
 * is unavailable; a ready signal that comes later still makes it ready. An error is not a
 * failure on its own (the camera reports its zoom and torch through the same callback): one
 * while starting fails the camera only if it has not started `CAMERA_ERROR_GRACE_MS` later,
 * and one once it runs is logged.
 */
export function useScannerCamera({ live }: Args) {
  const cameraRef = useRef<LiveScannerCameraHandle>(null);
  const [status, setStatus] = useState<ScannerCameraStatus>(CAMERA_STARTING);
  const [startError, setStartError] = useState(false);
  const starting = status.kind === "starting";

  useEffect(() => {
    if (!starting || !live) return;
    const timer = setTimeout(
      () => setStatus(cameraUnavailable(startError ? "failed" : "timeout")),
      startError ? CAMERA_ERROR_GRACE_MS : CAMERA_START_TIMEOUT_MS,
    );
    return () => clearTimeout(timer);
  }, [live, starting, startError]);

  /** A newly opened scanner waits for the camera again. */
  const resetCamera = useCallback(() => {
    setStatus(statusOnOpen);
    setStartError(false);
  }, []);
  const onReady = useCallback(() => setStatus(CAMERA_READY), []);
  const onError = useCallback((error: Error) => {
    console.warn("[scanner] camera error", error.message.split("\n")[0]);
    setStartError(true);
  }, []);
  const onUnavailable = useCallback(() => setStatus(cameraUnavailable("missing")), []);

  return { cameraRef, status, resetCamera, onReady, onError, onUnavailable };
}

/**
 * Where the scanner's live camera stands. Capture works only once it is `ready`; until then
 * the shutter shows that it is starting, and a camera that cannot run says so in the
 * viewfinder and offers a photo instead. A tap on Capture is never a silent no-op.
 */

/**
 * Why the live camera cannot run:
 * - `missing`: this build has no native camera (Expo Go, or a Simulator build without ML Kit);
 * - `failed`: the camera reported an error while starting;
 * - `timeout`: it gave no ready signal in time (no camera device, as in the Simulator).
 */
export type CameraUnavailableReason = "missing" | "failed" | "timeout";

export type ScannerCameraStatus =
  | { kind: "starting" }
  | { kind: "ready" }
  | { kind: "unavailable"; reason: CameraUnavailableReason };

/** A camera that has not started after this long is treated as unavailable. */
export const CAMERA_START_TIMEOUT_MS = 4_000;

export const CAMERA_STARTING: ScannerCameraStatus = { kind: "starting" };
export const CAMERA_READY: ScannerCameraStatus = { kind: "ready" };

export function cameraUnavailable(reason: CameraUnavailableReason): ScannerCameraStatus {
  return { kind: "unavailable", reason };
}

/**
 * The status a newly opened scanner starts from. A build without the native camera stays
 * that way while the app runs, so it is not asked again.
 */
export function statusOnOpen(current: ScannerCameraStatus): ScannerCameraStatus {
  return current.kind === "unavailable" && current.reason === "missing" ? current : CAMERA_STARTING;
}

/** The i18n key the viewfinder shows for an unavailable camera. */
export function cameraUnavailableKey(reason: CameraUnavailableReason): string {
  switch (reason) {
    case "missing":
      return "chat.math_scan_camera_needs_build";
    case "failed":
      return "chat.math_scan_camera_unavailable";
    case "timeout":
      return "chat.math_scan_camera_off";
  }
}

import {
  CAMERA_READY,
  CAMERA_STARTING,
  cameraUnavailable,
  cameraUnavailableKey,
  statusOnOpen,
} from "@/features/scanner/model/cameraStatus";

it("starts again on every open, except in a build without the camera", () => {
  expect(statusOnOpen(CAMERA_READY)).toEqual(CAMERA_STARTING);
  expect(statusOnOpen(cameraUnavailable("timeout"))).toEqual(CAMERA_STARTING);
  expect(statusOnOpen(cameraUnavailable("failed"))).toEqual(CAMERA_STARTING);
  expect(statusOnOpen(cameraUnavailable("missing"))).toEqual(cameraUnavailable("missing"));
});

it.each([
  ["missing", "chat.math_scan_camera_needs_build"],
  ["failed", "chat.math_scan_camera_unavailable"],
  ["timeout", "chat.math_scan_camera_off"],
] as const)("words an unavailable camera (%s)", (reason, key) => {
  expect(cameraUnavailableKey(reason)).toBe(key);
});

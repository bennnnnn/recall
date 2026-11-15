/**
 * How the scanner takes its still photo. A scan is a reading, not a snapshot: no camera click,
 * as other maths scanners do (it clicked like the camera until 2026-11-13). The OS still plays
 * the sound where the law requires one (Japan, Korea) and on iPhones before iOS 18, which
 * cannot silence it.
 */
export function scanPhotoOptions(supportsDistortionCorrection: boolean) {
  return {
    flashMode: "off" as const,
    enableShutterSound: false,
    enableDistortionCorrection: supportsDistortionCorrection,
  };
}

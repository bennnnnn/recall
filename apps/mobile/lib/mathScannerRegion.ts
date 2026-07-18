/**
 * Pure geometry for the math-scanner crop region — kept separate from
 * MathEquationScanner.tsx so the resize/move/crop math is unit-testable
 * without mounting a camera view or driving gesture-handler.
 *
 * BUG FIX (feature-audit finding): the scanner used to crop a fixed
 * full-width horizontal band (height-only, pinch-to-resize) — fine for a
 * single typed equation line, but too narrow for a word problem, a
 * multi-line system, or a diagram, and impossible to reposition off-center.
 * A free-form rectangle (resizable AND movable) fits what's actually in the
 * photo instead of forcing the photo to fit a fixed band shape.
 */

/** Fractions of the screen's width/height, 0..1, top-left origin. */
export type ScanRegion = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export const MIN_REGION_RATIO = 0.12;
export const MAX_REGION_RATIO = 0.92;

export function defaultScanRegion(): ScanRegion {
  const width = 0.82;
  const height = 0.3;
  return { x: (1 - width) / 2, y: (1 - height) / 2, width, height };
}

/** Clamp a region's size to [MIN_REGION_RATIO, MAX_REGION_RATIO] on each
 * axis, then clamp its position so it stays fully inside the 0..1 screen. */
export function clampScanRegion(region: ScanRegion): ScanRegion {
  const width = Math.min(MAX_REGION_RATIO, Math.max(MIN_REGION_RATIO, region.width));
  const height = Math.min(MAX_REGION_RATIO, Math.max(MIN_REGION_RATIO, region.height));
  const x = Math.min(1 - width, Math.max(0, region.x));
  const y = Math.min(1 - height, Math.max(0, region.y));
  return { x, y, width, height };
}

/** Resize `base` around its own center by `scale`, then re-clamp. */
export function scaleScanRegion(base: ScanRegion, scale: number): ScanRegion {
  const cx = base.x + base.width / 2;
  const cy = base.y + base.height / 2;
  const width = base.width * scale;
  const height = base.height * scale;
  return clampScanRegion({ x: cx - width / 2, y: cy - height / 2, width, height });
}

/** Translate `base` by a ratio delta, then re-clamp (size is unchanged;
 * the position clamp alone keeps it fully on-screen). */
export function translateScanRegion(base: ScanRegion, dxRatio: number, dyRatio: number): ScanRegion {
  return clampScanRegion({ ...base, x: base.x + dxRatio, y: base.y + dyRatio });
}

/**
 * Map a screen-space (ratio) region to pixel crop coordinates for
 * ImageManipulator, given the captured photo's actual pixel dimensions.
 * Assumes the camera preview fills the window edge-to-edge at "cover" scale
 * (CameraView's default, same assumption the original band-only crop made).
 */
export function regionToImageCrop(
  region: ScanRegion,
  imageWidth: number,
  imageHeight: number,
): { originX: number; originY: number; width: number; height: number } {
  const originX = Math.max(0, Math.min(imageWidth - 1, Math.round(region.x * imageWidth)));
  const originY = Math.max(0, Math.min(imageHeight - 1, Math.round(region.y * imageHeight)));
  const width = Math.max(1, Math.min(imageWidth - originX, Math.round(region.width * imageWidth)));
  const height = Math.max(1, Math.min(imageHeight - originY, Math.round(region.height * imageHeight)));
  return { originX, originY, width, height };
}

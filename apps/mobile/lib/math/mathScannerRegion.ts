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

export type ScanCorner = "tl" | "tr" | "bl" | "br";

/** Resize by dragging one corner. The opposite corner stays put until the
 * min-size clamp kicks in; then the whole region is re-clamped on-screen. */
export function resizeScanRegionFromCorner(
  base: ScanRegion,
  corner: ScanCorner,
  dxRatio: number,
  dyRatio: number,
): ScanRegion {
  let left = base.x;
  let top = base.y;
  let right = base.x + base.width;
  let bottom = base.y + base.height;
  if (corner === "tl" || corner === "bl") left += dxRatio;
  if (corner === "tr" || corner === "br") right += dxRatio;
  if (corner === "tl" || corner === "tr") top += dyRatio;
  if (corner === "bl" || corner === "br") bottom += dyRatio;

  if (right - left < MIN_REGION_RATIO) {
    if (corner === "tl" || corner === "bl") left = right - MIN_REGION_RATIO;
    else right = left + MIN_REGION_RATIO;
  }
  if (bottom - top < MIN_REGION_RATIO) {
    if (corner === "tl" || corner === "tr") top = bottom - MIN_REGION_RATIO;
    else bottom = top + MIN_REGION_RATIO;
  }
  return clampScanRegion({
    x: left,
    y: top,
    width: right - left,
    height: bottom - top,
  });
}

export function regionsClose(a: ScanRegion, b: ScanRegion, epsilon = 1e-3): boolean {
  return (
    Math.abs(a.x - b.x) < epsilon &&
    Math.abs(a.y - b.y) < epsilon &&
    Math.abs(a.width - b.width) < epsilon &&
    Math.abs(a.height - b.height) < epsilon
  );
}

export function regionIsDefault(region: ScanRegion): boolean {
  return regionsClose(clampScanRegion(region), clampScanRegion(defaultScanRegion()));
}

/** CameraView zoom is 0..1 (fraction of device max). */
export function clampCameraZoom(zoom: number): number {
  if (!Number.isFinite(zoom)) return 0;
  return Math.min(1, Math.max(0, zoom));
}

export const FOCUS_SQUARE_SIZE = 72;

export type FocusInRegion = { x: number; y: number; size: number };

/**
 * Map a tap that is already in crop-local pixels to a focus-square center
 * that stays fully inside the rectangle. Null when the tap is outside.
 * The square shrinks if the crop is smaller than `squareSize`.
 */
export function clampFocusInRegion(
  localX: number,
  localY: number,
  regionWidth: number,
  regionHeight: number,
  squareSize = FOCUS_SQUARE_SIZE,
): FocusInRegion | null {
  if (
    !Number.isFinite(localX) ||
    !Number.isFinite(localY) ||
    !Number.isFinite(regionWidth) ||
    !Number.isFinite(regionHeight) ||
    regionWidth <= 0 ||
    regionHeight <= 0 ||
    localX < 0 ||
    localY < 0 ||
    localX > regionWidth ||
    localY > regionHeight
  ) {
    return null;
  }
  const size = Math.min(squareSize, regionWidth, regionHeight);
  const half = size / 2;
  return {
    x: Math.min(Math.max(localX, half), regionWidth - half),
    y: Math.min(Math.max(localY, half), regionHeight - half),
    size,
  };
}

/** Map a pinch `scale` onto CameraView zoom. Scale 1 keeps `startZoom`. */
export function zoomFromPinch(startZoom: number, scale: number): number {
  const nextScale = Number.isFinite(scale) ? scale : 1;
  return clampCameraZoom(startZoom + (nextScale - 1) * 0.5);
}

/**
 * Map a screen-space (ratio) region to pixel crop coordinates for
 * ImageManipulator. CameraView fills the window with object-fit cover;
 * pass the window size so letterboxed overflow is subtracted. Defaults
 * keep the 1:1 mapping when window size equals the photo.
 */
export function regionToImageCrop(
  region: ScanRegion,
  imageWidth: number,
  imageHeight: number,
  windowWidth = imageWidth,
  windowHeight = imageHeight,
): { originX: number; originY: number; width: number; height: number } {
  const scale = Math.max(windowWidth / imageWidth, windowHeight / imageHeight);
  const displayedW = imageWidth * scale;
  const displayedH = imageHeight * scale;
  const coverOriginX = (displayedW - windowWidth) / 2;
  const coverOriginY = (displayedH - windowHeight) / 2;
  const imgX = (region.x * windowWidth + coverOriginX) / scale;
  const imgY = (region.y * windowHeight + coverOriginY) / scale;
  const imgW = (region.width * windowWidth) / scale;
  const imgH = (region.height * windowHeight) / scale;
  const originX = Math.max(0, Math.min(imageWidth - 1, Math.round(imgX)));
  const originY = Math.max(0, Math.min(imageHeight - 1, Math.round(imgY)));
  const width = Math.max(1, Math.min(imageWidth - originX, Math.round(imgW)));
  const height = Math.max(1, Math.min(imageHeight - originY, Math.round(imgH)));
  return { originX, originY, width, height };
}

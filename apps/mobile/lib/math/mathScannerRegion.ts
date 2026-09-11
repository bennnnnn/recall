/**
 * Pure geometry for the math-scanner crop region — kept separate from
 * MathEquationScanner.tsx so the resize/move/crop math is unit-testable
 * without mounting a camera view or driving gesture-handler.
 *
 * `'worklet'` lets Reanimated run these on the UI thread. The directive is
 * an inert string in Jest / Node.
 */

/** Fractions of the screen's width/height, 0..1, top-left origin. */
export type ScanRegion = {
  x: number;
  y: number;
  width: number;
  height: number;
};

/** Ratio insets that keep the crop out from under top/bottom chrome. */
export type ScanChromeInset = {
  top: number;
  right: number;
  bottom: number;
  left: number;
};

export const MIN_REGION_RATIO = 0.12;
export const MAX_REGION_RATIO = 0.92;
export const DEFAULT_REGION_WIDTH = 0.82;
export const DEFAULT_REGION_HEIGHT = 0.3;

/** Matches `Space.minTouch`. Handles shrink toward HANDLE_HIT_MIN. */
export const HANDLE_HIT_MAX = 44;
export const HANDLE_HIT_MIN = 16;

/** Pixel chrome used to derive `ScanChromeInset` (matches MathScannerChrome). */
export const SCANNER_TOP_CONTROL_PX = 44;
export const SCANNER_SHUTTER_PX = 76;

export const ZERO_INSET: ScanChromeInset = { top: 0, right: 0, bottom: 0, left: 0 };

export function scanChromeInset(
  windowWidth: number,
  windowHeight: number,
  safe: { top: number; bottom: number },
): ScanChromeInset {
  if (windowWidth <= 0 || windowHeight <= 0) return ZERO_INSET;
  const topPx = safe.top + 8 + SCANNER_TOP_CONTROL_PX + 8;
  const bottomPx = Math.max(safe.bottom, 16) + 12 + SCANNER_SHUTTER_PX + 12;
  return {
    top: Math.min(0.4, topPx / windowHeight),
    right: 0,
    bottom: Math.min(0.4, bottomPx / windowHeight),
    left: 0,
  };
}

export function defaultScanRegion(inset: ScanChromeInset = ZERO_INSET): ScanRegion {
  const width = DEFAULT_REGION_WIDTH;
  const height = DEFAULT_REGION_HEIGHT;
  return clampScanRegion({ x: (1 - width) / 2, y: (1 - height) / 2, width, height }, inset);
}

/** Clamp a region's size, then keep it inside the inset box (or 0..1). */
export function clampScanRegion(
  region: ScanRegion,
  inset: ScanChromeInset = ZERO_INSET,
): ScanRegion {
  "worklet";
  const availW = Math.max(0, 1 - inset.left - inset.right);
  const availH = Math.max(0, 1 - inset.top - inset.bottom);
  const minW = Math.min(MIN_REGION_RATIO, availW);
  const minH = Math.min(MIN_REGION_RATIO, availH);
  const maxW = Math.min(MAX_REGION_RATIO, availW);
  const maxH = Math.min(MAX_REGION_RATIO, availH);
  const width = Math.min(maxW, Math.max(minW, region.width));
  const height = Math.min(maxH, Math.max(minH, region.height));
  const x = Math.min(1 - inset.right - width, Math.max(inset.left, region.x));
  const y = Math.min(1 - inset.bottom - height, Math.max(inset.top, region.y));
  return { x, y, width, height };
}

export function handleHitSize(regionWidthPx: number, regionHeightPx: number): number {
  "worklet";
  const room = Math.min(regionWidthPx, regionHeightPx);
  if (!(room > 0)) return HANDLE_HIT_MIN;
  const size = Math.min(HANDLE_HIT_MAX, Math.max(HANDLE_HIT_MIN, room * 0.4));
  return size;
}

/** Resize `base` around its own center by `scale`, then re-clamp. */
export function scaleScanRegion(
  base: ScanRegion,
  scale: number,
  inset: ScanChromeInset = ZERO_INSET,
): ScanRegion {
  "worklet";
  const cx = base.x + base.width / 2;
  const cy = base.y + base.height / 2;
  const width = base.width * scale;
  const height = base.height * scale;
  return clampScanRegion({ x: cx - width / 2, y: cy - height / 2, width, height }, inset);
}

/** Translate `base` by a ratio delta, then re-clamp. */
export function translateScanRegion(
  base: ScanRegion,
  dxRatio: number,
  dyRatio: number,
  inset: ScanChromeInset = ZERO_INSET,
): ScanRegion {
  "worklet";
  return clampScanRegion({ ...base, x: base.x + dxRatio, y: base.y + dyRatio }, inset);
}

export type ScanCorner = "tl" | "tr" | "bl" | "br";

/** Resize by dragging one corner. The opposite corner stays put until min-size. */
export function resizeScanRegionFromCorner(
  base: ScanRegion,
  corner: ScanCorner,
  dxRatio: number,
  dyRatio: number,
  inset: ScanChromeInset = ZERO_INSET,
): ScanRegion {
  "worklet";
  let left = base.x;
  let top = base.y;
  let right = base.x + base.width;
  let bottom = base.y + base.height;
  if (corner === "tl" || corner === "bl") left += dxRatio;
  if (corner === "tr" || corner === "br") right += dxRatio;
  if (corner === "tl" || corner === "tr") top += dyRatio;
  if (corner === "bl" || corner === "br") bottom += dyRatio;

  const availW = Math.max(0, 1 - inset.left - inset.right);
  const availH = Math.max(0, 1 - inset.top - inset.bottom);
  const minW = Math.min(MIN_REGION_RATIO, availW);
  const minH = Math.min(MIN_REGION_RATIO, availH);

  if (right - left < minW) {
    if (corner === "tl" || corner === "bl") left = right - minW;
    else right = left + minW;
  }
  if (bottom - top < minH) {
    if (corner === "tl" || corner === "tr") top = bottom - minH;
    else bottom = top + minH;
  }
  return clampScanRegion(
    {
      x: left,
      y: top,
      width: right - left,
      height: bottom - top,
    },
    inset,
  );
}

export function regionsClose(a: ScanRegion, b: ScanRegion, epsilon = 1e-3): boolean {
  return (
    Math.abs(a.x - b.x) < epsilon &&
    Math.abs(a.y - b.y) < epsilon &&
    Math.abs(a.width - b.width) < epsilon &&
    Math.abs(a.height - b.height) < epsilon
  );
}

export function regionIsDefault(
  region: ScanRegion,
  inset: ScanChromeInset = ZERO_INSET,
): boolean {
  return regionsClose(clampScanRegion(region, inset), clampScanRegion(defaultScanRegion(inset), inset));
}

/** CameraView zoom is 0..1 (fraction of device max). */
export function clampCameraZoom(zoom: number): number {
  "worklet";
  if (!Number.isFinite(zoom)) return 0;
  return Math.min(1, Math.max(0, zoom));
}

/** Map a pinch `scale` onto CameraView zoom. Scale 1 keeps `startZoom`. */
export function zoomFromPinch(startZoom: number, scale: number): number {
  "worklet";
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

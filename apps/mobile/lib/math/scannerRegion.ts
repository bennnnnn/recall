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

/** Ratio insets that keep the crop out from under top/bottom chrome, and the smallest frame. */
export type ScanChromeInset = {
  top: number;
  right: number;
  bottom: number;
  left: number;
  /**
   * The smallest frame, as ratios of the screen: `MIN_REGION_PX` both ways. Absent, it is
   * `MIN_REGION_RATIO` of each side: on a phone twice as tall as wide, a frame twice as tall
   * as wide (about 80 points by 40 on the S23), too tall to frame one line.
   */
  minWidth?: number;
  minHeight?: number;
};

export const MIN_REGION_RATIO = 0.12;
/** The smallest frame's side, in points: one printed line, with room for its handles. */
export const MIN_REGION_PX = 48;
export const MAX_REGION_RATIO = 0.92;
export const DEFAULT_REGION_WIDTH = 0.82;
export const DEFAULT_REGION_HEIGHT = 0.3;

/** Pixel chrome used to derive `ScanChromeInset` (matches MathScannerChrome). */
export const SCANNER_TOP_CONTROL_PX = 44;
export const SCANNER_SHUTTER_PX = 76;
/** A subject tab's pill at the default text size, and the room above and below it in its row. */
export const SCANNER_SUBJECT_TAB_PX = 36;
export const SCANNER_SUBJECT_ROW_PAD_PX = 4;
/**
 * The subject tabs' row at the default text size (ScannerSubjectSwitcher draws it from the two
 * above): the pill and its padding, the tabs' 44 pt target. A larger text size grows it, and
 * the chrome measures it then.
 */
export const SCANNER_SUBJECT_SWITCHER_PX = SCANNER_SUBJECT_TAB_PX + 2 * SCANNER_SUBJECT_ROW_PAD_PX;

const ZERO_INSET: ScanChromeInset = { top: 0, right: 0, bottom: 0, left: 0 };

export function scanChromeInset(
  windowWidth: number,
  windowHeight: number,
  safe: { top: number; bottom: number },
): ScanChromeInset {
  if (windowWidth <= 0 || windowHeight <= 0) return ZERO_INSET;
  const topPx = safe.top + 8 + SCANNER_TOP_CONTROL_PX + 8;
  const bottomPx =
    Math.max(safe.bottom, 16) + 12 + SCANNER_SHUTTER_PX + SCANNER_SUBJECT_SWITCHER_PX + 44;
  return {
    top: Math.min(0.4, topPx / windowHeight),
    right: 0,
    bottom: Math.min(0.4, bottomPx / windowHeight),
    left: 0,
    minWidth: Math.min(1, MIN_REGION_PX / windowWidth),
    minHeight: Math.min(1, MIN_REGION_PX / windowHeight),
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
  chrome?: ScanChromeInset,
): ScanRegion {
  "worklet";
  // Not a default parameter: those do not carry module values to the UI thread.
  const inset = chrome ?? ZERO_INSET;
  const availW = Math.max(0, 1 - inset.left - inset.right);
  const availH = Math.max(0, 1 - inset.top - inset.bottom);
  const minW = Math.min(inset.minWidth ?? MIN_REGION_RATIO, availW);
  const minH = Math.min(inset.minHeight ?? MIN_REGION_RATIO, availH);
  const maxW = Math.min(MAX_REGION_RATIO, availW);
  const maxH = Math.min(MAX_REGION_RATIO, availH);
  const width = Math.min(maxW, Math.max(minW, region.width));
  const height = Math.min(maxH, Math.max(minH, region.height));
  // A frame grown to the smallest size (a one-line fit) grows around its middle, so it
  // stays on what it framed instead of reaching right and down.
  const x = Math.min(1 - inset.right - width, Math.max(inset.left, region.x + (region.width - width) / 2));
  const y = Math.min(1 - inset.bottom - height, Math.max(inset.top, region.y + (region.height - height) / 2));
  return { x, y, width, height };
}

/** Resize `base` around its own center by `scale`, then re-clamp. */
export function scaleScanRegion(
  base: ScanRegion,
  scale: number,
  inset?: ScanChromeInset,
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
  inset?: ScanChromeInset,
): ScanRegion {
  "worklet";
  return clampScanRegion({ ...base, x: base.x + dxRatio, y: base.y + dyRatio }, inset);
}

/** A handle on the crop frame: an edge (top, bottom, left, right) or a corner. */
export type ScanHandle = "t" | "b" | "l" | "r" | "tl" | "tr" | "bl" | "br";
export const SCAN_HANDLES: readonly ScanHandle[] = ["tl", "t", "tr", "r", "br", "b", "bl", "l"];

/**
 * Resize by dragging an edge or a corner. Only the edges it holds move, and each stops at
 * the free screen and at the smallest and largest frame, so the opposite edges stay put
 * (a corner pushed off the screen used to shove the far side across instead).
 */
export function resizeScanRegion(
  base: ScanRegion,
  handle: ScanHandle,
  dxRatio: number,
  dyRatio: number,
  chrome?: ScanChromeInset,
): ScanRegion {
  "worklet";
  const inset = chrome ?? ZERO_INSET;
  const availW = Math.max(0, 1 - inset.left - inset.right);
  const availH = Math.max(0, 1 - inset.top - inset.bottom);
  const minW = Math.min(inset.minWidth ?? MIN_REGION_RATIO, availW);
  const minH = Math.min(inset.minHeight ?? MIN_REGION_RATIO, availH);
  const maxW = Math.min(MAX_REGION_RATIO, availW);
  const maxH = Math.min(MAX_REGION_RATIO, availH);
  let left = base.x;
  let top = base.y;
  let right = base.x + base.width;
  let bottom = base.y + base.height;
  if (handle.includes("l")) left = Math.min(right - minW, Math.max(inset.left, right - maxW, left + dxRatio));
  if (handle.includes("r")) right = Math.max(left + minW, Math.min(1 - inset.right, left + maxW, right + dxRatio));
  if (handle.includes("t")) top = Math.min(bottom - minH, Math.max(inset.top, bottom - maxH, top + dyRatio));
  if (handle.includes("b")) bottom = Math.max(top + minH, Math.min(1 - inset.bottom, top + maxH, bottom + dyRatio));
  return clampScanRegion({ x: left, y: top, width: right - left, height: bottom - top }, inset);
}

export function regionsClose(a: ScanRegion, b: ScanRegion, epsilon = 1e-3): boolean {
  return (
    Math.abs(a.x - b.x) < epsilon &&
    Math.abs(a.y - b.y) < epsilon &&
    Math.abs(a.width - b.width) < epsilon &&
    Math.abs(a.height - b.height) < epsilon
  );
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
 * Map a region of a view (ratios of the view) onto the image that view shows
 * with object-fit cover (ratios of the image, clamped to 0..1). The camera
 * preview covers the scanner, so the overflow the view hides is subtracted.
 * The capture crop and the live OCR region of interest both use this, so the
 * frame the student sees is the one that is read.
 */
export function viewRegionToImageRegion(
  region: ScanRegion,
  imageWidth: number,
  imageHeight: number,
  viewWidth = imageWidth,
  viewHeight = imageHeight,
): ScanRegion {
  const scale = Math.max(viewWidth / imageWidth, viewHeight / imageHeight);
  const displayedW = imageWidth * scale;
  const displayedH = imageHeight * scale;
  const left = (region.x * viewWidth + (displayedW - viewWidth) / 2) / displayedW;
  const top = (region.y * viewHeight + (displayedH - viewHeight) / 2) / displayedH;
  const right = left + (region.width * viewWidth) / displayedW;
  const bottom = top + (region.height * viewHeight) / displayedH;
  const x = Math.min(1, Math.max(0, left));
  const y = Math.min(1, Math.max(0, top));
  return {
    x,
    y,
    width: Math.max(0, Math.min(1, right) - x),
    height: Math.max(0, Math.min(1, bottom) - y),
  };
}

/**
 * Pixel crop for ImageManipulator of a view region over a covered image (see
 * `viewRegionToImageRegion`). Defaults keep the 1:1 mapping when the view
 * size equals the photo.
 */
export function regionToImageCrop(
  region: ScanRegion,
  imageWidth: number,
  imageHeight: number,
  viewWidth = imageWidth,
  viewHeight = imageHeight,
): { originX: number; originY: number; width: number; height: number } {
  const mapped = viewRegionToImageRegion(region, imageWidth, imageHeight, viewWidth, viewHeight);
  const originX = Math.max(0, Math.min(imageWidth - 1, Math.round(mapped.x * imageWidth)));
  const originY = Math.max(0, Math.min(imageHeight - 1, Math.round(mapped.y * imageHeight)));
  const width = Math.max(1, Math.min(imageWidth - originX, Math.round(mapped.width * imageWidth)));
  const height = Math.max(1, Math.min(imageHeight - originY, Math.round(mapped.height * imageHeight)));
  return { originX, originY, width, height };
}


/** Fit an imported photo inside the scanner chrome without cropping its edges. */
export function containedPhotoRegion(
  imageWidth: number,
  imageHeight: number,
  windowWidth: number,
  windowHeight: number,
  inset: ScanChromeInset = ZERO_INSET,
): ScanRegion {
  if (![imageWidth, imageHeight, windowWidth, windowHeight].every((n) => Number.isFinite(n) && n > 0)) {
    throw new Error("Invalid photo dimensions");
  }
  const availableWidth = Math.min(MAX_REGION_RATIO, 1 - inset.left - inset.right);
  const availableHeight = Math.min(MAX_REGION_RATIO, 1 - inset.top - inset.bottom);
  const scale = Math.min(windowWidth * availableWidth / imageWidth, windowHeight * availableHeight / imageHeight);
  const width = imageWidth * scale / windowWidth;
  const height = imageHeight * scale / windowHeight;
  return {
    x: (1 + inset.left - inset.right - width) / 2,
    y: (1 + inset.top - inset.bottom - height) / 2,
    width,
    height,
  };
}

/** A box in a photo (ratios of it) as a region of the view the photo is contained in. */
export function photoBoxToViewRegion(box: ScanRegion, photoRegion: ScanRegion): ScanRegion {
  return {
    x: photoRegion.x + box.x * photoRegion.width,
    y: photoRegion.y + box.y * photoRegion.height,
    width: box.width * photoRegion.width,
    height: box.height * photoRegion.height,
  };
}

/** Intersect a screen crop with the imported image, excluding letterbox space. */
export function regionToContainedImageCrop(
  region: ScanRegion,
  imageRegion: ScanRegion,
  imageWidth: number,
  imageHeight: number,
): { originX: number; originY: number; width: number; height: number } {
  const left = Math.max(region.x, imageRegion.x);
  const top = Math.max(region.y, imageRegion.y);
  const right = Math.min(region.x + region.width, imageRegion.x + imageRegion.width);
  const bottom = Math.min(region.y + region.height, imageRegion.y + imageRegion.height);
  if (!(right > left && bottom > top)) throw new Error("Crop does not overlap the photo");
  const originX = Math.max(0, Math.min(imageWidth - 1, Math.round((left - imageRegion.x) / imageRegion.width * imageWidth)));
  const originY = Math.max(0, Math.min(imageHeight - 1, Math.round((top - imageRegion.y) / imageRegion.height * imageHeight)));
  const endX = Math.max(originX + 1, Math.min(imageWidth, Math.round((right - imageRegion.x) / imageRegion.width * imageWidth)));
  const endY = Math.max(originY + 1, Math.min(imageHeight, Math.round((bottom - imageRegion.y) / imageRegion.height * imageHeight)));
  return { originX, originY, width: endX - originX, height: endY - originY };
}

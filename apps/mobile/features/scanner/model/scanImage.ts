import { deleteAsync } from "expo-file-system/legacy";
import { ImageManipulator, type ImageRef, SaveFormat } from "expo-image-manipulator";

import { regionToContainedImageCrop, type ScanRegion } from "@/lib/math/scannerRegion";

/**
 * Longest edge of a scan crop sent to the reader. Mathpix and the vision
 * models read handwriting well at this size; a full-resolution crop only adds
 * upload time and the API's 4 MB cap (`SCAN_MAX_IMAGE_BYTES`).
 */
export const SCAN_MAX_EDGE = 2048;
export const SCAN_JPEG_QUALITY = 0.8;

type ImageSize = { width: number; height: number };
type PixelCrop = { originX: number; originY: number; width: number; height: number };

/** The downscale that brings a crop's long edge to `maxEdge`; null when it already fits. */
export function scanResize(
  size: ImageSize,
  maxEdge = SCAN_MAX_EDGE,
): { width: number } | { height: number } | null {
  if (Math.max(size.width, size.height) <= maxEdge) return null;
  return size.width >= size.height ? { width: maxEdge } : { height: maxEdge };
}

/**
 * Where a camera shot's cut came from: the photo as the camera saved it, and the cut's
 * rectangle in it. Solve cuts the student's crop from this photo, so the photo sent is
 * encoded once from the camera's, not again from the crop screen's copy (SCAN-05,
 * 2026-11-13 STEM audit).
 */
export type ShotSource = { uri: string; cut: PixelCrop };

/**
 * A crop drawn on a shot's cut (`inCut`, in the pixels of the cut as saved, `cutSize`: smaller
 * when it was downscaled), in the original photo's pixels, kept inside the photo (`photo`,
 * its decoded size).
 */
export function cropInSource(
  inCut: PixelCrop,
  source: ShotSource,
  cutSize: ImageSize,
  photo: ImageSize,
): PixelCrop {
  const sx = source.cut.width / cutSize.width;
  const sy = source.cut.height / cutSize.height;
  const originX = Math.min(photo.width - 1, Math.max(0, Math.round(source.cut.originX + inCut.originX * sx)));
  const originY = Math.min(photo.height - 1, Math.max(0, Math.round(source.cut.originY + inCut.originY * sy)));
  return {
    originX,
    originY,
    width: Math.max(1, Math.min(photo.width - originX, Math.round(inCut.width * sx))),
    height: Math.max(1, Math.min(photo.height - originY, Math.round(inCut.height * sy))),
  };
}

/**
 * The long edge the crop is sent at: what cutting it from the crop screen's copy gave, so
 * the photo's size does not change, only its second encode goes.
 */
export function sentEdge(inCut: PixelCrop, maxEdge = SCAN_MAX_EDGE): number {
  return Math.min(maxEdge, Math.max(inCut.width, inCut.height));
}

function validSize(image: ImageRef): ImageSize {
  const { width, height } = image;
  if (!(width > 0 && height > 0)) throw new Error("invalid image size");
  return { width, height };
}

/**
 * The image's size as the manipulator sees it (EXIF orientation applied), the
 * same space `cropScanImage` cuts in. React Native's Image.getSize can report
 * the stored, unrotated size instead.
 */
export async function measureScanImage(uri: string): Promise<ImageSize> {
  const context = ImageManipulator.manipulate(uri);
  let image: ImageRef | undefined;
  try {
    image = await context.renderAsync();
    return validSize(image);
  } finally {
    image?.release();
    context.release();
  }
}

/**
 * Crop and downscale a scan in one pass. `cropFor` gets the decoded size, so
 * the crop is computed in the space it is applied in.
 */
export async function cropScanImage(
  uri: string,
  cropFor: (size: ImageSize) => PixelCrop,
  maxEdge = SCAN_MAX_EDGE,
): Promise<{ uri: string } & ImageSize> {
  const context = ImageManipulator.manipulate(uri);
  let source: ImageRef | undefined;
  let result: ImageRef | undefined;
  try {
    source = await context.renderAsync();
    const crop = cropFor(validSize(source));
    context.crop(crop);
    const resize = scanResize(crop, maxEdge);
    if (resize) context.resize(resize);
    result = await context.renderAsync();
    const saved = await result.saveAsync({ compress: SCAN_JPEG_QUALITY, format: SaveFormat.JPEG });
    return { uri: saved.uri, width: saved.width, height: saved.height };
  } finally {
    result?.release();
    source?.release();
    context.release();
  }
}

/**
 * What Solve cuts: the frame drawn on the crop screen's still (`region` over the still's frame
 * on screen), from the camera's photo when the still is a camera shot's cut, so the photo is
 * encoded once, at the long edge cutting the still would have given (`maxEdge`); else from the
 * still, as before.
 */
export function solveCut(
  shot: ImageSize & { localUri: string; source?: ShotSource | null },
  region: ScanRegion,
  frame: ScanRegion,
): { uri: string; cropFor: (size: ImageSize) => PixelCrop; maxEdge?: number } {
  const source = shot.source;
  if (!source) {
    return {
      uri: shot.localUri,
      cropFor: (size) => regionToContainedImageCrop(region, frame, size.width, size.height),
    };
  }
  const inCut = regionToContainedImageCrop(region, frame, shot.width, shot.height);
  return {
    uri: source.uri,
    cropFor: (size) => cropInSource(inCut, source, shot, size),
    maxEdge: sentEdge(inCut),
  };
}

/** A copy of a scan no longer than `maxEdge` on its long side; the caller deletes it. */
export async function shrinkScanImage(uri: string, maxEdge: number): Promise<{ uri: string } & ImageSize> {
  const context = ImageManipulator.manipulate(uri);
  let source: ImageRef | undefined;
  let result: ImageRef | undefined;
  try {
    source = await context.renderAsync();
    const resize = scanResize(validSize(source), maxEdge);
    if (resize) context.resize(resize);
    result = await context.renderAsync();
    const saved = await result.saveAsync({ compress: SCAN_JPEG_QUALITY, format: SaveFormat.JPEG });
    return { uri: saved.uri, width: saved.width, height: saved.height };
  } finally {
    result?.release();
    source?.release();
    context.release();
  }
}

/** Delete a scan file from the cache. Idempotent; a failed delete never blocks the scanner. */
function discardScanFile(uri: string): void {
  void deleteAsync(uri, { idempotent: true }).catch(() => undefined);
}

/**
 * The cache files one scanner owns: every capture, picked copy and crop until
 * it is handed to the composer as the chat attachment or discarded.
 */
export class ScanFiles {
  private readonly owned = new Set<string>();

  track(uri: string): void {
    this.owned.add(uri);
  }

  /** The composer owns this file now; the scanner never deletes it. */
  handOff(uri: string): void {
    this.owned.delete(uri);
  }

  discard(uri: string): void {
    if (!this.owned.delete(uri)) return;
    discardScanFile(uri);
  }

  discardAll(): void {
    for (const uri of this.owned) discardScanFile(uri);
    this.owned.clear();
  }
}

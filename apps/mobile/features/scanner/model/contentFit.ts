/**
 * Where a scan's problem is in its still, from the text lines ML Kit finds there
 * (`readTextLines`). The crop screen moves its frame there; the student can still move it
 * before Solve, and nothing is cut until then.
 */

/** A box in an image, as ratios of its width and height (0..1). */
export type ImageBox = { x: number; y: number; width: number; height: number };

type Size = { width: number; height: number };

/** A line shorter than this share of the image is a speck or a smudge, not text. */
const MIN_LINE_HEIGHT = 0.006;
/** A fit that keeps this much of the photo trims nothing worth moving the frame for. */
const TRIM_WORTH = 0.9;
/** Edges this close are the same edge. */
const SAME_EDGE = 0.005;

/**
 * The frame for a still's text, or null when it would not move.
 *
 * - With `aim` (a camera shot: where the live frame was in the shot) it never gets smaller
 *   than the aim. It grows to take in whole a line the aim cut, since the student aimed at
 *   that line; a line whose middle is above or below the aim is the next problem, not a cut
 *   one. Text it cannot see, a diagram or faint handwriting, is never cut off.
 * - Without (a photo or a file) it takes every line, dropping the margins and the desk,
 *   with a wide margin: a diagram or handwriting next to the text may be unread.
 *
 * Padded by a share of the image or part of a line, whichever is more.
 */
export function fitToContent(lines: ImageBox[], size: Size, aim: ImageBox | null): ImageBox | null {
  const text = lines.filter((line) => line.height >= MIN_LINE_HEIGHT && line.width > 0);
  const kept = aim ? text.filter((line) => cutByAim(line, aim)) : text;
  if (kept.length === 0) return null;
  const margin = aim ? { share: 0.02, lines: 0.5 } : { share: 0.06, lines: 1 };
  const padded = clampToImage(pad(union(kept), padding(kept, size, margin)));
  const fit = aim ? union([padded, aim]) : padded;
  if (aim) return sameBox(fit, aim) ? null : fit;
  return fit.width * fit.height >= TRIM_WORTH ? null : fit;
}

/** A line the aim cuts: its middle is within the aim's height, and part of it is inside. */
function cutByAim(line: ImageBox, aim: ImageBox): boolean {
  const middle = line.y + line.height / 2;
  return middle >= aim.y && middle <= aim.y + aim.height
    && line.x < aim.x + aim.width && line.x + line.width > aim.x;
}

function union(boxes: ImageBox[]): ImageBox {
  const left = Math.min(...boxes.map((box) => box.x));
  const top = Math.min(...boxes.map((box) => box.y));
  const right = Math.max(...boxes.map((box) => box.x + box.width));
  const bottom = Math.max(...boxes.map((box) => box.y + box.height));
  return { x: left, y: top, width: right - left, height: bottom - top };
}

/**
 * A share of the image's short side, or some of the middle line's height, whichever is more:
 * the same in pixels on every side, as ratios of each.
 */
function padding(lines: ImageBox[], size: Size, margin: { share: number; lines: number }): { x: number; y: number } {
  const heights = lines.map((line) => line.height * size.height).sort((a, b) => a - b);
  const median = heights[Math.floor(heights.length / 2)] ?? 0;
  const px = Math.max(margin.share * Math.min(size.width, size.height), median * margin.lines);
  return { x: px / size.width, y: px / size.height };
}

function pad(box: ImageBox, by: { x: number; y: number }): ImageBox {
  return { x: box.x - by.x, y: box.y - by.y, width: box.width + 2 * by.x, height: box.height + 2 * by.y };
}

function clampToImage(box: ImageBox): ImageBox {
  const x = Math.max(0, box.x);
  const y = Math.max(0, box.y);
  return { x, y, width: Math.min(1, box.x + box.width) - x, height: Math.min(1, box.y + box.height) - y };
}

function sameBox(a: ImageBox, b: ImageBox): boolean {
  return Math.abs(a.x - b.x) < SAME_EDGE && Math.abs(a.y - b.y) < SAME_EDGE
    && Math.abs(a.x + a.width - (b.x + b.width)) < SAME_EDGE
    && Math.abs(a.y + a.height - (b.y + b.height)) < SAME_EDGE;
}

/** Room a camera shot keeps around the live frame, as a share of the frame's size each side. */
const SHOT_CONTEXT = 0.2;

/** How long a shot's cut may be, so the part aimed at keeps the reader's full `maxEdge`. */
export function shotCutMaxEdge(maxEdge: number): number {
  return Math.round(maxEdge * (1 + 2 * SHOT_CONTEXT));
}

type PixelCrop = { originX: number; originY: number; width: number; height: number };

/**
 * A camera shot's cut: the live frame with room around it, so the crop screen can widen the
 * frame over a line it cut, and where the live frame lies in that cut (`aim`).
 */
export function shotCrop(frame: PixelCrop, size: Size): { crop: PixelCrop; aim: ImageBox } {
  const left = Math.max(0, Math.round(frame.originX - frame.width * SHOT_CONTEXT));
  const top = Math.max(0, Math.round(frame.originY - frame.height * SHOT_CONTEXT));
  const right = Math.min(size.width, Math.round(frame.originX + frame.width * (1 + SHOT_CONTEXT)));
  const bottom = Math.min(size.height, Math.round(frame.originY + frame.height * (1 + SHOT_CONTEXT)));
  const crop = { originX: left, originY: top, width: right - left, height: bottom - top };
  return { crop, aim: boxIn(frame, crop) };
}

/** A pixel crop as ratios of the image (or of an outer crop) it lies in. */
export function boxIn(inner: PixelCrop, outer: PixelCrop | Size): ImageBox {
  const originX = "originX" in outer ? outer.originX : 0;
  const originY = "originY" in outer ? outer.originY : 0;
  return {
    x: (inner.originX - originX) / outer.width,
    y: (inner.originY - originY) / outer.height,
    width: inner.width / outer.width,
    height: inner.height / outer.height,
  };
}

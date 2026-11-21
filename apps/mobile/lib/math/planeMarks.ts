/**
 * The marks a coordinate plane draws in screen space, from points the server placed:
 * equal-side ticks, a right angle's square, a vector's arrowhead, where a label sits. They
 * are sized in pixels, so they look the same however far the plane reaches; none of them
 * moves a point or works one out.
 */
import { type LabelSide } from "@/lib/math/pointsGraph";

export type Px = { px: number; py: number };

const TICK_HALF = 4;
const TICK_GAP = 4;
const SQUARE = 9;
const ARROW = 8;
const LABEL_GAP = 6;
const LABEL_DROP = 14;
const SEGMENT_LABEL_GAP = 10;

function unit(from: Px, to: Px): Px | null {
  const dx = to.px - from.px;
  const dy = to.py - from.py;
  const length = Math.hypot(dx, dy);
  return length > 0 ? { px: dx / length, py: dy / length } : null;
}

/** Short strokes across a segment's middle: one, two or three, for sides of equal length. */
export function tickStrokes(start: Px, end: Px, count: number): [Px, Px][] {
  const along = unit(start, end);
  if (!along || count < 1) return [];
  const across = { px: -along.py, py: along.px };
  const mid = { px: (start.px + end.px) / 2, py: (start.py + end.py) / 2 };
  return Array.from({ length: count }, (_, i) => {
    const shift = (i - (count - 1) / 2) * TICK_GAP;
    const at = { px: mid.px + along.px * shift, py: mid.py + along.py * shift };
    return [
      { px: at.px - across.px * TICK_HALF, py: at.py - across.py * TICK_HALF },
      { px: at.px + across.px * TICK_HALF, py: at.py + across.py * TICK_HALF },
    ];
  });
}

/** The small square of a right angle at `at`, its sides along the arms towards `a` and `b`. */
export function rightAngleSquare(at: Px, a: Px, b: Px): Px[] {
  const u = unit(at, a);
  const v = unit(at, b);
  if (!u || !v) return [];
  return [
    { px: at.px + u.px * SQUARE, py: at.py + u.py * SQUARE },
    { px: at.px + (u.px + v.px) * SQUARE, py: at.py + (u.py + v.py) * SQUARE },
    { px: at.px + v.px * SQUARE, py: at.py + v.py * SQUARE },
  ];
}

/** An arrowhead at `end`, pointing the way the segment runs. */
export function arrowHead(start: Px, end: Px): Px[] {
  const along = unit(start, end);
  if (!along) return [];
  const back = { px: end.px - along.px * ARROW, py: end.py - along.py * ARROW };
  const across = { px: -along.py * (ARROW / 2), py: along.px * (ARROW / 2) };
  return [end, { px: back.px + across.px, py: back.py + across.py }, { px: back.px - across.px, py: back.py - across.py }];
}

/**
 * A point's label beside it on its side (away from its shape), turned back inside the plane
 * when it would run off an edge.
 */
export function pointLabelAt(
  at: Px,
  side: LabelSide,
  textWidth: number,
  frame: { width: number; height: number; pad: number },
): { x: number; y: number; anchor: "start" | "end" } {
  let east = side.endsWith("e");
  if (east && at.px + LABEL_GAP + textWidth > frame.width - frame.pad / 2) east = false;
  else if (!east && at.px - LABEL_GAP - textWidth < frame.pad / 2) east = true;
  let north = side.startsWith("n");
  if (north && at.py - LABEL_GAP - LABEL_DROP < 0) north = false;
  else if (!north && at.py + LABEL_DROP > frame.height) north = true;
  return {
    x: east ? at.px + LABEL_GAP : at.px - LABEL_GAP,
    y: north ? at.py - LABEL_GAP : at.py + LABEL_DROP,
    anchor: east ? "start" : "end",
  };
}

/** A segment's label at its middle, set off to the side away from the figure's middle. */
export function segmentLabelAt(start: Px, end: Px, middle: Px): Px {
  const mid = { px: (start.px + end.px) / 2, py: (start.py + end.py) / 2 };
  const along = unit(start, end);
  if (!along) return mid;
  let across = { px: -along.py, py: along.px };
  const away = (mid.px - middle.px) * across.px + (mid.py - middle.py) * across.py;
  // Level with the middle: above the segment, where a label reads first.
  if (away < 0 || (away === 0 && across.py > 0)) across = { px: -across.px, py: -across.py };
  return { px: mid.px + across.px * SEGMENT_LABEL_GAP, py: mid.py + across.py * SEGMENT_LABEL_GAP + 4 };
}

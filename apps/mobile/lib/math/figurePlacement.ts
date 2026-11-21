/**
 * Where a figure's text goes: each label tries the places beside its own part, nearest
 * first, and takes the first whose text crosses no stroke (a side, a mark, an arc, a dot)
 * and no label already placed. Text is never written over the drawing; when every place
 * touches something, the one touching least wins.
 */

export type Px = { x: number; y: number };
export type FigureLabel = Px & { text: string; anchor: "start" | "middle" | "end" };
export type Stroke = [Px, Px];

/** A label character's width and its height above and below the baseline, at the label size. */
export const LABEL_CHAR = 7;
export const LABEL_ASCENT = 11;
export const LABEL_DESCENT = 3;
/** The clear space a label keeps from every stroke and every other label. */
const CLEAR = 2;

type Box = { x0: number; y0: number; x1: number; y1: number };

export function labelStart(label: FigureLabel): number {
  const w = label.text.length * LABEL_CHAR;
  return label.anchor === "start" ? label.x : label.anchor === "end" ? label.x - w : label.x - w / 2;
}

function box(label: FigureLabel): Box {
  const x0 = labelStart(label);
  return {
    x0: x0 - CLEAR,
    x1: x0 + label.text.length * LABEL_CHAR + CLEAR,
    y0: label.y - LABEL_ASCENT - CLEAR,
    y1: label.y + LABEL_DESCENT + CLEAR,
  };
}

/** Whether the stroke from `a` to `b` passes through the box (Liang–Barsky clipping). */
function crosses([a, b]: Stroke, r: Box): boolean {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  let lo = 0;
  let hi = 1;
  const edges: [number, number][] = [
    [-dx, a.x - r.x0],
    [dx, r.x1 - a.x],
    [-dy, a.y - r.y0],
    [dy, r.y1 - a.y],
  ];
  for (const [p, q] of edges) {
    if (p === 0) {
      if (q < 0) return false;
      continue;
    }
    const t = q / p;
    if (p < 0) lo = Math.max(lo, t);
    else hi = Math.min(hi, t);
    if (lo > hi) return false;
  }
  return true;
}

function overlaps(a: Box, b: Box): boolean {
  return a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;
}

/** How many strokes and other labels the label's text touches: what a reader would see
 * written over the drawing. */
export function labelTouches(label: FigureLabel, strokes: Stroke[], others: FigureLabel[]): number {
  const r = box(label);
  return strokes.filter((stroke) => crosses(stroke, r)).length + others.filter((other) => overlaps(r, box(other))).length;
}

/** Places each label in turn at its first clear spot; `options` lists each one's places, best first. */
export function placeLabels(options: FigureLabel[][], strokes: Stroke[]): FigureLabel[] {
  const out: FigureLabel[] = [];
  for (const places of options) {
    let best: FigureLabel | undefined;
    let fewest = Infinity;
    for (const place of places) {
      const count = labelTouches(place, strokes, out);
      if (count < fewest) {
        best = place;
        fewest = count;
      }
      if (count === 0) break;
    }
    if (best) out.push(best);
  }
  return out;
}

/** A polyline as its strokes. */
export function strokesOf(points: Px[]): Stroke[] {
  return points.slice(1).map((p, i) => [points[i], p]);
}

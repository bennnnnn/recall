/**
 * Worklet-safe copies of the graph viewport/tick math from graphBlock.ts and
 * graphViewport.ts. Reanimated does not workletize imported functions, so the
 * Skia explorer keeps its own self-contained versions here — every function
 * carries the directive and the module imports nothing. They are still plain
 * pure functions and run fine on the JS thread (unit tests exercise them
 * directly); keep behavior in sync with the JS originals.
 */

export type GraphViewW = {
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
};

const MIN_SPAN_W = 0.002;
const MAX_SPAN_W = 1e4;

export function clampGraphViewW(view: GraphViewW): GraphViewW {
  "worklet";
  let { xMin, xMax, yMin, yMax } = view;
  if (
    !(xMax > xMin) ||
    !(yMax > yMin) ||
    !Number.isFinite(xMax - xMin) ||
    !Number.isFinite(yMax - yMin)
  ) {
    // defaultInteractiveBounds(1.7)
    return { xMin: -6, xMax: 6, yMin: -6 / 1.7, yMax: 6 / 1.7 };
  }
  const xSpan = xMax - xMin;
  const ySpan = yMax - yMin;
  const cx = (xMin + xMax) / 2;
  const cy = (yMin + yMax) / 2;
  let scale = 1;
  const minSpan = Math.min(xSpan, ySpan);
  const maxSpan = Math.max(xSpan, ySpan);
  if (minSpan < MIN_SPAN_W) scale = MIN_SPAN_W / minSpan;
  if (maxSpan * scale > MAX_SPAN_W) scale = MAX_SPAN_W / maxSpan;
  if (scale === 1) return view;
  return {
    xMin: cx - (xSpan * scale) / 2,
    xMax: cx + (xSpan * scale) / 2,
    yMin: cy - (ySpan * scale) / 2,
    yMax: cy + (ySpan * scale) / 2,
  };
}

/** Pinch scale > 1 zooms in (smaller world window) around a data-space focal point. */
export function zoomGraphViewW(
  start: GraphViewW,
  scale: number,
  focalX: number,
  focalY: number,
): GraphViewW {
  "worklet";
  const s = Number.isFinite(scale) && scale > 0 ? scale : 1;
  return clampGraphViewW({
    xMin: focalX - (focalX - start.xMin) / s,
    xMax: focalX + (start.xMax - focalX) / s,
    yMin: focalY - (focalY - start.yMin) / s,
    yMax: focalY + (start.yMax - focalY) / s,
  });
}

/** Drag right moves the plane with the finger (x window shifts left). */
export function panGraphViewW(
  start: GraphViewW,
  dxPx: number,
  dyPx: number,
  width: number,
  height: number,
  pad: number,
): GraphViewW {
  "worklet";
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  if (!(innerW > 0) || !(innerH > 0)) return start;
  const xSpan = start.xMax - start.xMin;
  const ySpan = start.yMax - start.yMin;
  const dx = (-dxPx / innerW) * xSpan;
  const dy = (dyPx / innerH) * ySpan;
  return {
    xMin: start.xMin + dx,
    xMax: start.xMax + dx,
    yMin: start.yMin + dy,
    yMax: start.yMax + dy,
  };
}

export function mapPointW(
  x: number,
  y: number,
  bounds: GraphViewW,
  width: number,
  height: number,
  pad: number,
): { px: number; py: number } {
  "worklet";
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  const px = pad + ((x - bounds.xMin) / (bounds.xMax - bounds.xMin || 1)) * innerW;
  const py = pad + innerH - ((y - bounds.yMin) / (bounds.yMax - bounds.yMin || 1)) * innerH;
  return { px, py };
}

export function unmapPointW(
  px: number,
  py: number,
  bounds: GraphViewW,
  width: number,
  height: number,
  pad: number,
): { x: number; y: number } {
  "worklet";
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  const x = bounds.xMin + ((px - pad) / (innerW || 1)) * (bounds.xMax - bounds.xMin);
  const y = bounds.yMax - ((py - pad) / (innerH || 1)) * (bounds.yMax - bounds.yMin);
  return { x, y };
}

function niceStepW(raw: number): number {
  "worklet";
  if (!(raw > 0) || !Number.isFinite(raw)) return 1;
  const exp = Math.floor(Math.log10(raw));
  const mag = 10 ** exp;
  const f = raw / mag;
  const nf = f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10;
  return nf * mag;
}

/** Enough ticks that a ±6 window still labels every integer. */
export function tickCountW(min: number, max: number): number {
  "worklet";
  const span = max - min;
  if (!(span > 0) || !Number.isFinite(span)) return 7;
  return Math.min(13, Math.max(7, Math.ceil(span) + 1));
}

export function formatTickW(n: number): string {
  "worklet";
  if (!Number.isFinite(n)) return "";
  const rounded = Math.round(n);
  if (Math.abs(n - rounded) < 1e-9) return Object.is(rounded, -0) ? "0" : String(rounded);
  return Object.is(n, -0) ? "0" : String(Number(n.toPrecision(12)));
}

/** Short "(2.5, 6.25)" callout formatting — 2 decimals max, trailing zeros trimmed. */
export function formatShortW(n: number): string {
  "worklet";
  if (!Number.isFinite(n)) return "";
  const r = Math.round(n * 100) / 100;
  return Object.is(r, -0) ? "0" : String(r);
}

/** Even ticks inside a view window (e.g. −6, −4, …, 6). */
export function axisTicksW(min: number, max: number): number[] {
  "worklet";
  if (!Number.isFinite(min) || !Number.isFinite(max) || max <= min) return [];
  const step = niceStepW((max - min) / Math.max(1, tickCountW(min, max) - 1));
  if (!Number.isFinite(step) || step <= 0) return [];
  const start = Math.ceil((min - 1e-12) / step) * step;
  const ticks: number[] = [];
  const seen = new Set<string>();
  for (let v = start, count = 0; count < 64 && v <= max + step * 1e-9; v += step, count += 1) {
    const n = Math.abs(v) < step * 1e-9 ? 0 : Number(v.toPrecision(12));
    if (n < min - 1e-9 || n > max + 1e-9) continue;
    const key = formatTickW(n);
    if (seen.has(key)) continue;
    seen.add(key);
    ticks.push(n);
  }
  return ticks;
}

/** Nearest sampled point to a data-space x, or null when the series is empty. */
export function nearestSampleW(
  points: [number, number][],
  x: number,
): { x: number; y: number; index: number } | null {
  "worklet";
  let best: { x: number; y: number; index: number } | null = null;
  let bestDist = Infinity;
  for (let i = 0; i < points.length; i += 1) {
    const [px, py] = points[i];
    if (!Number.isFinite(px) || !Number.isFinite(py)) continue;
    const dist = Math.abs(px - x);
    if (dist < bestDist) {
      bestDist = dist;
      best = { x: px, y: py, index: i };
    }
  }
  return best;
}

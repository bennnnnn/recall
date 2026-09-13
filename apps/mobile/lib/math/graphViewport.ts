export type GraphView = {
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
};

/** Default school window: x ≈ −6…6 so labels include −3…3 at unit steps. */
export const DEFAULT_GRAPH_X_HALF = 6;
const MIN_SPAN = 0.002;
const MAX_SPAN = 1e4;

export function defaultInteractiveBounds(plotAspect: number): GraphView {
  const aspect = Number.isFinite(plotAspect) && plotAspect > 0.3 ? plotAspect : 1.7;
  const xHalf = DEFAULT_GRAPH_X_HALF;
  const yHalf = xHalf / aspect;
  return { xMin: -xHalf, xMax: xHalf, yMin: -yHalf, yMax: yHalf };
}

export function clampGraphView(view: GraphView): GraphView {
  let { xMin, xMax, yMin, yMax } = view;
  if (!(xMax > xMin) || !(yMax > yMin) || !Number.isFinite(xMax - xMin) || !Number.isFinite(yMax - yMin)) {
    return defaultInteractiveBounds(1.7);
  }
  const xSpan = xMax - xMin;
  const ySpan = yMax - yMin;
  const cx = (xMin + xMax) / 2;
  const cy = (yMin + yMax) / 2;
  let scale = 1;
  const minSpan = Math.min(xSpan, ySpan);
  const maxSpan = Math.max(xSpan, ySpan);
  if (minSpan < MIN_SPAN) scale = MIN_SPAN / minSpan;
  if (maxSpan * scale > MAX_SPAN) scale = MAX_SPAN / maxSpan;
  if (scale === 1) return view;
  return {
    xMin: cx - (xSpan * scale) / 2,
    xMax: cx + (xSpan * scale) / 2,
    yMin: cy - (ySpan * scale) / 2,
    yMax: cy + (ySpan * scale) / 2,
  };
}

/** Pinch scale > 1 zooms in (smaller world window) around a data-space focal point. */
export function zoomGraphView(
  start: GraphView,
  scale: number,
  focalX: number,
  focalY: number,
): GraphView {
  const s = Number.isFinite(scale) && scale > 0 ? scale : 1;
  return clampGraphView({
    xMin: focalX - (focalX - start.xMin) / s,
    xMax: focalX + (start.xMax - focalX) / s,
    yMin: focalY - (focalY - start.yMin) / s,
    yMax: focalY + (start.yMax - focalY) / s,
  });
}

/** Drag right moves the plane with the finger (x window shifts left). */
export function panGraphView(
  start: GraphView,
  dxPx: number,
  dyPx: number,
  width: number,
  height: number,
  pad: number,
): GraphView {
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

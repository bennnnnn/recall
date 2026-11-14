/**
 * The window a graph card and its explorer open on.
 *
 * Ordinary graphs open on the familiar ±6 school window, grown just enough to
 * show what a reader looks for on the curve as drawn: a vertex or turning
 * point, where it crosses the axes or another curve, a line or point off to
 * one side, the whole of a circle. The fixed window alone cut the vertex off
 * y = x² − 4 and left y = 7, x = 8 and (8, 3) off the card entirely.
 *
 * A curve whose features sit together in a corner of that window is focused on
 * them instead: y = x² − 4x + 3 has its roots, vertex and y-intercept between
 * x = 0 and 3, and the ±6 window left half the card empty. The features are read
 * off the curve as drawn, for the window only; the points the card labels are
 * the server's (`GraphSpec.marks`).
 */
import { equalScaleGraphBounds, functionPlotBounds } from "@/lib/math/graphBlock";
import { parseGraphRelation, sampleGraphExpr } from "@/lib/math/graphExpr";
import { type GraphSpec } from "@/lib/math/graphSpec";
import { defaultInteractiveBounds, type GraphView } from "@/lib/math/graphViewport";

type Point = [number, number];

/** More turning points and crossings than a school polynomial has: a wave, read in view only. */
const MANY_FEATURES = 6;
/** A feature this close to the frame (share of the span) is too tight to read. */
const EDGE_MARGIN = 0.06;
/** Room left past a feature the window grew to show (share of the new span). */
const FEATURE_PAD = 0.15;
/** A y-intercept that would stretch the window past this factor is left out: y = (x − 8)². */
const Y_INTERCEPT_STRETCH = 3;
/** A grown window this much taller than square keeps its own y scale: y = x³ − 100x. */
const TALL = 1.25;
/** A plotted point's expression, "(8, 3)", unlike a bracketed "(x - 8)^2". */
const POINT_LIST = /^\s*\(\s*[-+]?\d*\.?\d+\s*,/;
/** Samples read for features across the server's x-range. */
const FEATURE_SAMPLES = 400;
/** A focused window is at least this wide, so the curve keeps some shape around its features. */
const FOCUS_MIN_SPAN = 6;
/** Room left around the features a window focuses on (share of their span, at least a unit). */
const FOCUS_PAD = 0.25;
/** Features closer than this in x and y are one place: y = x² keeps the school window. */
const ONE_PLACE = 0.5;

type Curve = { expr: string; points: Point[]; segments?: Point[][] };

/**
 * A curve's runs, split at its poles: sampled the way the card draws it, so a
 * pole the server left joined (y = 1/(x − 2) + 3) is no turning point. The
 * server's own samples when the phone cannot read the expression.
 */
function curveRuns(curve: Curve, variable: string, xMin: number, xMax: number): Point[][] {
  const relation = parseGraphRelation(curve.expr, variable);
  if (relation && relation.cmp === "=" && xMax > xMin) {
    const sampled = sampleGraphExpr(relation.node, xMin, xMax, FEATURE_SAMPLES);
    if (sampled.points.length >= 2) return sampled.segments ?? [sampled.points];
  }
  if (curve.segments && curve.segments.length > 1) {
    return curve.segments.filter((run) => run.length >= 2);
  }
  return curve.points.length ? [curve.points] : [];
}

function turningPoints(run: Point[]): Point[] {
  const out: Point[] = [];
  let rising = 0;
  for (let i = 1; i < run.length; i += 1) {
    const step = Math.sign(run[i][1] - run[i - 1][1]);
    if (step === 0) continue;
    if (rising !== 0 && step !== rising) out.push(run[i - 1]);
    rising = step;
  }
  return out;
}

/** Where y changes sign. A tail rounded to 0 (e^x at x = −10) never crosses. */
function signChanges(run: Point[], value: (point: Point, i: number) => number): Point[] {
  const out: Point[] = [];
  let last = -1;
  for (let i = 0; i < run.length; i += 1) {
    const v = value(run[i], i);
    if (v === 0 || !Number.isFinite(v)) continue;
    if (last >= 0) {
      const w = value(run[last], last);
      if (w * v < 0) {
        const t = w / (w - v);
        const x = run[last][0] + t * (run[i][0] - run[last][0]);
        out.push([x, run[last][1] + t * (run[i][1] - run[last][1])]);
      }
    }
    last = i;
  }
  return out;
}

function axisCrossings(run: Point[]): Point[] {
  return signChanges(run, ([, y]) => y).map(([x]) => [x, 0]);
}

/** Where two curves sampled on the same x grid meet: y = x² and y = 2x + 8. */
function meetings(a: Point[], b: Point[]): Point[] {
  if (a.length !== b.length || a.some(([x], i) => x !== b[i][0])) return [];
  return signChanges(a, ([, y], i) => y - b[i][1]);
}

/** Where a run crosses x = 0, when a run spans it (never across a pole between runs). */
function yIntercept(run: Point[]): Point | null {
  for (let i = 1; i < run.length; i += 1) {
    const [x0, y0] = run[i - 1];
    const [x1, y1] = run[i];
    if (x0 <= 0 && x1 >= 0 && x1 > x0) return [0, y0 + ((0 - x0) / (x1 - x0)) * (y1 - y0)];
  }
  return null;
}

function isClosed(points: Point[]): boolean {
  const first = points[0];
  const last = points[points.length - 1];
  return points.length > 2 && first[0] === last[0] && first[1] === last[1];
}

function extremes(points: Point[]): Point[] {
  const xs = points.map(([x]) => x);
  const ys = points.map(([, y]) => y);
  return [
    [Math.min(...xs), Math.min(...ys)],
    [Math.max(...xs), Math.max(...ys)],
  ];
}

/** `runs`: the curve as drawn, when the window may focus on its features (no pole, no wave). */
type Features = { main: Point[]; intercepts: Point[]; closed: boolean; runs: Point[][] | null };

/** What the window must show: features of the curve as drawn, or the points as plotted. */
function graphFeatures(spec: GraphSpec, view: GraphView): Features {
  if (spec.type === "vertical") {
    return { main: Number.isFinite(spec.x) ? [[Number(spec.x), 0]] : [], intercepts: [], closed: false, runs: null };
  }
  if (spec.type !== "function") return { main: [], intercepts: [], closed: false, runs: null };
  const curves: Curve[] = [{ expr: spec.expr, points: spec.points, segments: spec.segments }];
  if (spec.expr2 && spec.points2?.length) {
    curves.push({ expr: spec.expr2, points: spec.points2, segments: spec.segments2 });
  }
  // A circle or ellipse is drawn whole; plotted points ("(8, 3)") are each shown.
  const plotted = (curve: Curve) => curve.points.length === 1 || POINT_LIST.test(curve.expr);
  if (curves.some((curve) => plotted(curve) || isClosed(curve.points))) {
    const all = curves.flatMap(({ points }) => points);
    return { main: extremes(all), intercepts: [], closed: curves.some(({ points }) => isClosed(points)), runs: null };
  }
  const xs = curves.flatMap(({ points }) => points.map(([x]) => x));
  const variable = spec.variable ?? "x";
  const sampled = curves.map((curve) => curveRuns(curve, variable, Math.min(...xs), Math.max(...xs)));
  const runs = sampled.flat();
  let main = runs.flatMap((run) => [...turningPoints(run), ...axisCrossings(run)]);
  if (sampled.length === 2 && sampled[0].length === 1 && sampled[1].length === 1) {
    main.push(...meetings(sampled[0][0], sampled[1][0]));
  }
  const wave = main.length > MANY_FEATURES;
  if (wave) main = main.filter(([x]) => x >= view.xMin && x <= view.xMax);
  main.push(...(spec.marks ?? []).map(({ x, y }): Point => [x, y]));
  const intercepts = runs.map(yIntercept).filter((point): point is Point => point != null);
  // Only a graph of y = f(x) the phone reads, in one piece: a circle or a relation in x and
  // y keeps its fit and its true axis ratio.
  const functions = curves.every((curve) => parseGraphRelation(curve.expr, variable)?.cmp === "=");
  const focusable = functions && !wave && sampled.every((curve) => curve.length === 1);
  return { main, intercepts, closed: false, runs: focusable ? runs : null };
}

function span(values: number[]): [number, number] {
  return [Math.min(...values), Math.max(...values)];
}

/**
 * The window around a curve's features when they sit closer together than the school
 * window: their x-range with room around it, and the curve's own y-values over it, kept
 * within reach of the features (y = x² − 4x + 3 shows its arms, not their climb to 11).
 * Null when the features are one place, or would need the school window or more.
 */
function focusView(points: Point[], runs: Point[][], school: GraphView): GraphView | null {
  const finite = points.filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y));
  if (finite.length < 2) return null;
  const [x0, x1] = span(finite.map(([x]) => x));
  const [y0, y1] = span(finite.map(([, y]) => y));
  if (x1 - x0 < ONE_PLACE && y1 - y0 < ONE_PLACE) return null;
  const pad = Math.max(1, (x1 - x0) * FOCUS_PAD);
  const half = Math.max(FOCUS_MIN_SPAN, x1 - x0 + 2 * pad) / 2;
  const mid = (x0 + x1) / 2;
  const [xMin, xMax] = [mid - half, mid + half];
  if (xMax - xMin >= school.xMax - school.xMin) return null;
  const reach = Math.max(y1 - y0, FOCUS_MIN_SPAN / 2);
  const ys = runs
    .flat()
    .filter(([x, y]) => x >= xMin && x <= xMax && y >= y0 - reach && y <= y1 + reach)
    .map(([, y]) => y);
  const [lo, hi] = span([y0, y1, ...ys]);
  const yPad = Math.max(ONE_PLACE, (hi - lo) * FEATURE_PAD * 0.5);
  return { xMin, xMax, yMin: lo - yPad, yMax: hi + yPad };
}

/** The y-intercept joins the features unless it is far off them: y = (x − 8)² meets x = 0 at 64. */
function nearIntercepts(main: Point[], intercepts: Point[]): Point[] {
  const ys = main.map(([, y]) => y);
  if (!ys.length) return intercepts;
  const [lo, hi] = span(ys);
  const reach = Y_INTERCEPT_STRETCH * Math.max(hi - lo, FOCUS_MIN_SPAN);
  return intercepts.filter(([, y]) => y >= lo - reach && y <= hi + reach);
}

function growAxis(lo: number, hi: number, values: number[]): [number, number] {
  const margin = (hi - lo) * EDGE_MARGIN;
  const low = Math.min(...values);
  const high = Math.max(...values);
  if (low >= lo + margin && high <= hi - margin) return [lo, hi];
  const pad = (Math.max(hi, high) - Math.min(lo, low)) * FEATURE_PAD;
  return [low < lo + margin ? Math.min(lo, low - pad) : lo, high > hi - margin ? Math.max(hi, high + pad) : hi];
}

function grow(view: GraphView, points: Point[]): GraphView {
  const finite = points.filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y));
  if (!finite.length) return view;
  const [xMin, xMax] = growAxis(view.xMin, view.xMax, finite.map(([x]) => x));
  const [yMin, yMax] = growAxis(view.yMin, view.yMax, finite.map(([, y]) => y));
  const same = xMin === view.xMin && xMax === view.xMax && yMin === view.yMin && yMax === view.yMax;
  return same ? view : { xMin, xMax, yMin, yMax };
}

/** The larger of the two spans, in x units at 1:1. */
function size(view: GraphView, aspect: number): number {
  return Math.max(view.xMax - view.xMin, (view.yMax - view.yMin) * aspect);
}

function fitView(spec: GraphSpec, plotAspect: number): GraphView {
  const view = defaultInteractiveBounds(plotAspect);
  const aspect = Number.isFinite(plotAspect) && plotAspect > 0.3 ? plotAspect : 1.7;
  const { main, intercepts, closed, runs } = graphFeatures(spec, view);
  const focused = runs ? focusView([...main, ...nearIntercepts(main, intercepts)], runs, view) : null;
  if (focused) {
    const tallFocus = (focused.yMax - focused.yMin) * aspect > (focused.xMax - focused.xMin) * TALL;
    return tallFocus ? focused : equalScaleGraphBounds(focused, aspect);
  }
  let fitted = grow(view, main);
  const withIntercept = grow(fitted, intercepts);
  if (size(withIntercept, aspect) <= size(fitted, aspect) * Y_INTERCEPT_STRETCH) fitted = withIntercept;
  if (fitted === view) return view;
  const tall = (fitted.yMax - fitted.yMin) * aspect > (fitted.xMax - fitted.xMin) * TALL;
  return tall && !closed ? fitted : equalScaleGraphBounds(fitted, aspect);
}

/** The learner gave the x-range in π ("from 0 to 2π"): the x axis is labelled in π. */
export function xAxisInPi(spec: GraphSpec): boolean {
  if (spec.type !== "function" || !spec.domain_explicit) return false;
  const ends = [Number(spec.x_min), Number(spec.x_max)];
  return (
    ends.some((x) => x !== 0) &&
    ends.every((x) => Number.isFinite(x) && Math.abs((x * 2) / Math.PI - Math.round((x * 2) / Math.PI)) < 1e-9)
  );
}

/**
 * Initial interactive viewport for a verified graph.
 *
 * When the learner explicitly asks for an x-domain, keep those exact
 * horizontal endpoints and use the sampled curve only to choose a readable
 * vertical crop. Otherwise the school window, fitted to the curve's features.
 * The view is still fully pinchable and pannable after it opens.
 */
export function interactiveFunctionBounds(spec: GraphSpec, plotAspect: number): GraphView {
  if (spec.type !== "function" || !spec.domain_explicit) return fitView(spec, plotAspect);
  const xMin = Number(spec.x_min);
  const xMax = Number(spec.x_max);
  if (!Number.isFinite(xMin) || !Number.isFinite(xMax) || xMax <= xMin) {
    return fitView(spec, plotAspect);
  }
  const fitted = functionPlotBounds(spec.points, spec.points2, plotAspect);
  return { ...fitted, ...statedRangeHeight(spec, fitted), xMin, xMax };
}

/** Room above and below a curve over the learner's range, as a share of its height. */
const STATED_RANGE_PAD = 0.08;

/** A step between two samples this large a share of the curve's height is a pole. */
const POLE_JUMP = 0.25;

/** The curve jumps somewhere: split at a pole (tan x), or a pole the samples run across. */
function jumps(points: [number, number][], height: number): boolean {
  return points.some(([, y], i) => i > 0 && Math.abs(y - points[i - 1][1]) > height * POLE_JUMP);
}

/**
 * Over a range the learner named, the curve is what they asked to see: a crop that misses it
 * (a reservoir's depth from 144 m down to 96 m over weeks 0 to 12 drew an empty −1…5 card,
 * 2026-11-13) gives way to the curve's own heights. A curve with a pole keeps the crop.
 */
function statedRangeHeight(spec: GraphSpec, fitted: GraphView): Pick<GraphView, "yMin" | "yMax"> {
  const curves = [spec.points, spec.points2 ?? []];
  const ys = curves.flat().map(([, y]) => y).filter(Number.isFinite);
  if (!ys.length || (spec.segments?.length ?? 0) > 1 || (spec.segments2?.length ?? 0) > 1) return fitted;
  const [low, high] = [Math.min(...ys), Math.max(...ys)];
  if (fitted.yMin <= low && fitted.yMax >= high) return fitted;
  if (curves.some((points) => jumps(points, high - low))) return fitted;
  const pad = Math.max(high - low, 1) * STATED_RANGE_PAD;
  return { yMin: low - pad, yMax: high + pad };
}

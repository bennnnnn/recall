/**
 * A server-drawn figure (```geometry `figure`): read it, then fit it to the card.
 *
 * The server sends every point in the question's own units; this scales the drawing to
 * the width it has, flips y for the screen and places each label beside its part: a
 * side's length outside the figure, an angle's size inside it, a vertex's letter away
 * from the middle. Nothing here works out a coordinate the server did not send.
 */
import {
  MAX_GEOMETRY_DIMENSION,
  type FigureAngle,
  type FigureArc,
  type FigurePoint,
  type FigureSegment,
  type FigureSpec,
} from "@/lib/math/geometryTypes";

type Px = { x: number; y: number };

type FigureLabel = Px & { text: string; anchor: "start" | "middle" | "end" };
type FigureLine = { from: Px; to: Px; dashed: boolean };
type FigureLayout = {
  width: number;
  height: number;
  faces: Px[][];
  lines: FigureLine[];
  /** Equal-length ticks and parallel arrowheads: short strokes over their side. */
  marks: [Px, Px][];
  arcs: { points: Px[]; dashed: boolean }[];
  angleArcs: Px[][];
  dots: Px[];
  labels: FigureLabel[];
};

const MAX_POINTS = 80;
const MAX_LABEL = 24;
/** Room around the drawing for its labels. */
const PAD = 24;
/** The card's own margin a label keeps, and a label character's width and height above
 * its baseline, at the label size. */
const EDGE = 2;
const LABEL_CHAR = 7;
const LABEL_ASCENT = 11;
/** A figure is at most this tall against its width, so a tall solid stays in the card. */
const MAX_HEIGHT_SHARE = 0.85;
const ARC_STEP_DEG = 4;
const ANGLE_RADIUS = 16;
const ANGLE_LABEL_GAP = 14;
const RIGHT_SIDE = 11;
const LABEL_GAP = 10;
const NAME_GAP = 12;
const TICK = 5;
const TICK_SPACING = 4;
const ARROW = 6;

function finite(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && Math.abs(value) <= MAX_GEOMETRY_DIMENSION;
}

function name(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 && value.length <= 8 ? value : null;
}

function label(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim().slice(0, MAX_LABEL) : undefined;
}

function count(value: unknown): number {
  return typeof value === "number" && Number.isInteger(value) ? Math.max(0, Math.min(3, value)) : 0;
}

function rows(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.filter((row): row is Record<string, unknown> => !!row && typeof row === "object") : [];
}

function readPoints(value: unknown): FigurePoint[] | null {
  const points: FigurePoint[] = [];
  for (const row of rows(value).slice(0, MAX_POINTS)) {
    const id = name(row.name);
    if (!id || !finite(row.x) || !finite(row.y)) return null;
    points.push({ name: id, x: row.x, y: row.y, show: row.show === true, dot: row.dot === true });
  }
  return points.length ? points : null;
}

function readSegments(value: unknown, known: Set<string>): FigureSegment[] | null {
  const out: FigureSegment[] = [];
  for (const row of rows(value)) {
    const a = name(row.a);
    const b = name(row.b);
    if (!a || !b || a === b || !known.has(a) || !known.has(b)) return null;
    const at = typeof row.label_at === "number" && row.label_at >= 0.1 && row.label_at <= 0.9 ? row.label_at : 0.5;
    out.push({
      a,
      b,
      label: label(row.label),
      dashed: row.dashed === true,
      ticks: count(row.ticks),
      arrows: count(row.arrows),
      label_at: at,
    });
  }
  return out;
}

function readArcs(value: unknown, known: Set<string>): FigureArc[] | null {
  const out: FigureArc[] = [];
  for (const row of rows(value)) {
    const center = name(row.center);
    const start = row.start === undefined ? 0 : row.start;
    const end = row.end === undefined ? 360 : row.end;
    if (!center || !known.has(center) || !finite(row.rx) || !finite(row.ry)) return null;
    if (row.rx <= 0 || row.ry <= 0 || !finite(start) || !finite(end) || end <= start) return null;
    out.push({ center, rx: row.rx, ry: row.ry, start, end, dashed: row.dashed === true });
  }
  return out;
}

function readAngles(value: unknown, known: Set<string>): FigureAngle[] | null {
  const out: FigureAngle[] = [];
  for (const row of rows(value)) {
    const at = name(row.at);
    const a = name(row.a);
    const b = name(row.b);
    if (!at || !a || !b || ![at, a, b].every((id) => known.has(id))) return null;
    out.push({ at, a, b, label: label(row.label), right: row.right === true });
  }
  return out;
}

/** A figure fence as the server sends it, or null: a part naming a point it lacks is refused. */
export function parseFigure(row: Record<string, unknown>): FigureSpec | null {
  if (row.type !== "figure") return null;
  const points = readPoints(row.points);
  if (!points) return null;
  const known = new Set(points.map((point) => point.name));
  if (known.size !== points.length) return null;
  const segments = readSegments(row.segments, known);
  const arcs = readArcs(row.arcs, known);
  const angles = readAngles(row.angles, known);
  if (!segments || !arcs || !angles || (!segments.length && !arcs.length)) return null;
  const faces = Array.isArray(row.faces)
    ? row.faces.filter((face): face is string[] => Array.isArray(face) && face.length >= 3 && face.every((id) => known.has(String(id))))
    : [];
  return { type: "figure", shape: String(row.shape ?? "figure"), points, segments, arcs, angles, faces };
}

function arcPoints(arc: FigureArc, center: FigurePoint): { x: number; y: number }[] {
  const out: { x: number; y: number }[] = [];
  const steps = Math.max(2, Math.ceil((arc.end - arc.start) / ARC_STEP_DEG));
  for (let i = 0; i <= steps; i += 1) {
    const turn = ((arc.start + ((arc.end - arc.start) * i) / steps) * Math.PI) / 180;
    out.push({ x: center.x + arc.rx * Math.cos(turn), y: center.y + arc.ry * Math.sin(turn) });
  }
  return out;
}

function unit(dx: number, dy: number): Px {
  const length = Math.hypot(dx, dy) || 1;
  return { x: dx / length, y: dy / length };
}

function anchorFor(direction: Px): FigureLabel["anchor"] {
  if (direction.x > 0.35) return "start";
  if (direction.x < -0.35) return "end";
  return "middle";
}

/** Text sits on its baseline: one pushed down drops by a line so it clears its part. */
function placed(at: Px, direction: Px, gap: number, text: string): FigureLabel {
  const x = at.x + direction.x * gap;
  const y = at.y + direction.y * gap + (direction.y > 0.35 ? 9 : direction.y < -0.35 ? 0 : 4);
  return { x, y, text, anchor: anchorFor(direction) };
}

type Mapper = (x: number, y: number) => Px;
type Pads = { left: number; right: number; top: number; bottom: number };

function fit(spec: FigureSpec, width: number, pads: Pads): { map: Mapper; height: number } {
  const byName = new Map(spec.points.map((point) => [point.name, point]));
  const extent = [
    ...spec.points,
    ...spec.arcs.flatMap((arc) => {
      const center = byName.get(arc.center);
      return center ? arcPoints(arc, center) : [];
    }),
  ];
  const xs = extent.map((p) => p.x);
  const ys = extent.map((p) => p.y);
  const minX = Math.min(...xs);
  const maxY = Math.max(...ys);
  const spanX = Math.max(Math.max(...xs) - minX, 1e-9);
  const spanY = Math.max(maxY - Math.min(...ys), 1e-9);
  const inner = Math.max(40, width - pads.left - pads.right);
  const scale = Math.min(inner / spanX, (width * MAX_HEIGHT_SHARE) / spanY);
  const offset = pads.left + (inner - spanX * scale) / 2;
  return {
    map: (x, y) => ({ x: offset + (x - minX) * scale, y: pads.top + (maxY - y) * scale }),
    height: spanY * scale + pads.top + pads.bottom,
  };
}

/** How far a label's text reaches past the card on each side, by an estimate of its width. */
function overflow(labels: FigureLabel[], width: number, height: number): Pads {
  const out = { left: 0, right: 0, top: 0, bottom: 0 };
  for (const label of labels) {
    const w = label.text.length * LABEL_CHAR;
    const start = label.anchor === "start" ? label.x : label.anchor === "end" ? label.x - w : label.x - w / 2;
    out.left = Math.max(out.left, EDGE - start);
    out.right = Math.max(out.right, start + w - (width - EDGE));
    out.top = Math.max(out.top, EDGE + LABEL_ASCENT - label.y);
    out.bottom = Math.max(out.bottom, label.y + EDGE - height);
  }
  return out;
}

function segmentMarks(from: Px, to: Px, segment: FigureSegment): [Px, Px][] {
  const along = unit(to.x - from.x, to.y - from.y);
  const across = { x: -along.y, y: along.x };
  const mid = { x: (from.x + to.x) / 2, y: (from.y + to.y) / 2 };
  const marks: [Px, Px][] = [];
  const ticks = segment.ticks ?? 0;
  for (let i = 0; i < ticks; i += 1) {
    const shift = (i - (ticks - 1) / 2) * TICK_SPACING;
    const c = { x: mid.x + along.x * shift, y: mid.y + along.y * shift };
    marks.push([{ x: c.x - across.x * TICK, y: c.y - across.y * TICK }, { x: c.x + across.x * TICK, y: c.y + across.y * TICK }]);
  }
  const arrows = segment.arrows ?? 0;
  for (let i = 0; i < arrows; i += 1) {
    const tip = { x: mid.x + along.x * (i * ARROW), y: mid.y + along.y * (i * ARROW) };
    for (const side of [1, -1]) {
      marks.push([tip, { x: tip.x - along.x * ARROW + across.x * side * ARROW * 0.7, y: tip.y - along.y * ARROW + across.y * side * ARROW * 0.7 }]);
    }
  }
  return marks;
}

/** Where a side's label goes: beside its middle, outside the face that holds it (else away
 * from the figure's middle). */
function segmentLabel(from: Px, to: Px, middle: Px, text: string, share = 0.5): FigureLabel {
  const along = unit(to.x - from.x, to.y - from.y);
  let normal = { x: -along.y, y: along.x };
  const mid = { x: from.x + (to.x - from.x) * share, y: from.y + (to.y - from.y) * share };
  const away = normal.x * (mid.x - middle.x) + normal.y * (mid.y - middle.y);
  if (away < -1e-6 || (Math.abs(away) <= 1e-6 && normal.y > 0)) normal = { x: -normal.x, y: -normal.y };
  return placed(mid, normal, LABEL_GAP, text);
}

/** The angle mark from the ray to `a` round to the ray to `b`, the short way, in screen space. */
function angleMark(at: Px, a: Px, b: Px, angle: FigureAngle): { path: Px[]; label?: FigureLabel } {
  const ua = unit(a.x - at.x, a.y - at.y);
  const ub = unit(b.x - at.x, b.y - at.y);
  if (angle.right) {
    const corner = { x: at.x + (ua.x + ub.x) * RIGHT_SIDE, y: at.y + (ua.y + ub.y) * RIGHT_SIDE };
    return {
      path: [
        { x: at.x + ua.x * RIGHT_SIDE, y: at.y + ua.y * RIGHT_SIDE },
        corner,
        { x: at.x + ub.x * RIGHT_SIDE, y: at.y + ub.y * RIGHT_SIDE },
      ],
    };
  }
  const from = Math.atan2(ua.y, ua.x);
  let sweep = Math.atan2(ub.y, ub.x) - from;
  while (sweep <= -Math.PI) sweep += 2 * Math.PI;
  while (sweep > Math.PI) sweep -= 2 * Math.PI;
  const steps = Math.max(2, Math.ceil(Math.abs(sweep) / ((ARC_STEP_DEG * Math.PI) / 180)));
  const path: Px[] = [];
  for (let i = 0; i <= steps; i += 1) {
    const turn = from + (sweep * i) / steps;
    path.push({ x: at.x + Math.cos(turn) * ANGLE_RADIUS, y: at.y + Math.sin(turn) * ANGLE_RADIUS });
  }
  if (!angle.label) return { path };
  const half = from + sweep / 2;
  const direction = { x: Math.cos(half), y: Math.sin(half) };
  return { path, label: placed(at, direction, ANGLE_RADIUS + ANGLE_LABEL_GAP, angle.label) };
}

function centroid(points: Px[]): Px {
  return {
    x: points.reduce((sum, p) => sum + p.x, 0) / points.length,
    y: points.reduce((sum, p) => sum + p.y, 0) / points.length,
  };
}

function build(spec: FigureSpec, width: number, pads: Pads): FigureLayout {
  const { map, height } = fit(spec, width, pads);
  const px = new Map(spec.points.map((point) => [point.name, map(point.x, point.y)]));
  const at = (id: string): Px => px.get(id) ?? { x: 0, y: 0 };
  const middle = centroid([...px.values()]);
  const byName = new Map(spec.points.map((point) => [point.name, point]));
  const layout: FigureLayout = { width, height, faces: [], lines: [], marks: [], arcs: [], angleArcs: [], dots: [], labels: [] };
  layout.faces = spec.faces.map((face) => face.map(at));
  for (const segment of spec.segments) {
    const from = at(segment.a);
    const to = at(segment.b);
    layout.lines.push({ from, to, dashed: segment.dashed === true });
    layout.marks.push(...segmentMarks(from, to, segment));
    if (!segment.label) continue;
    const face = spec.faces.find((names) => names.includes(segment.a) && names.includes(segment.b));
    const outside = face ? centroid(face.map(at)) : middle;
    layout.labels.push(segmentLabel(from, to, outside, segment.label, segment.label_at));
  }
  for (const arc of spec.arcs) {
    const center = byName.get(arc.center);
    if (center) layout.arcs.push({ points: arcPoints(arc, center).map((p) => map(p.x, p.y)), dashed: arc.dashed === true });
  }
  for (const angle of spec.angles) {
    const mark = angleMark(at(angle.at), at(angle.a), at(angle.b), angle);
    layout.angleArcs.push(mark.path);
    if (mark.label) layout.labels.push(mark.label);
  }
  for (const point of spec.points) {
    const p = at(point.name);
    if (point.dot) layout.dots.push(p);
    if (!point.show) continue;
    const away = unit(p.x - middle.x, p.y - middle.y);
    // A letter at the figure's middle (a circle's centre) sits up and to its left.
    const direction = away.x === 0 && away.y === 0 ? { x: -0.7, y: -0.7 } : away;
    layout.labels.push(placed(p, direction, NAME_GAP, point.name));
  }
  return layout;
}

/** The figure fitted to ``width``, its padding grown once so no label runs off the card. */
export function figureLayout(spec: FigureSpec, width: number): FigureLayout {
  const pads = { left: PAD, right: PAD, top: PAD, bottom: PAD };
  const first = build(spec, width, pads);
  const over = overflow(first.labels, first.width, first.height);
  if (over.left <= 0 && over.right <= 0 && over.top <= 0 && over.bottom <= 0) return first;
  return build(spec, width, {
    left: pads.left + Math.max(0, over.left),
    right: pads.right + Math.max(0, over.right),
    top: pads.top + Math.max(0, over.top),
    bottom: pads.bottom + Math.max(0, over.bottom),
  });
}

/** What a screen reader hears: the figure's letters and its stated values, in order. */
export function figureSpokenParts(spec: FigureSpec): string[] {
  const names = spec.points.filter((point) => point.show).map((point) => point.name);
  const values = [...spec.segments.map((segment) => segment.label), ...spec.angles.map((angle) => angle.label)];
  return [...names, ...values.filter((text): text is string => !!text)];
}

/**
 * Parsing and layout for the electric field diagram (`simulation` fence, type
 * `field`).
 *
 * The server traces every field line from the charges and sends each as the
 * polyline it follows, with one arrowhead per line (a point and the field's
 * direction there), the charges, the plates and the neutral points. Nothing
 * here works out a field: this file reads the spec as strictly as the server
 * wrote it and maps it onto the canvas with the ray diagram's world frame.
 */

import {
  guard,
  optionalList,
  optionalText,
  refuse,
  requireNumber,
  requirePoint,
  requireRecord,
} from "@/lib/fence/validate";
import { toScreen, worldTransform, type ScreenPoint, type WorldBounds } from "@/lib/physics/optics";

type WorldPoint = { x: number; y: number };

type FieldCharge = { at: WorldPoint; sign: 1 | -1; radius: number; label?: string };
type FieldPlate = { start: WorldPoint; end: WorldPoint; sign: 1 | -1 };
type FieldArrow = { at: WorldPoint; dx: number; dy: number };

export type FieldSpec = {
  charges: FieldCharge[];
  plates: FieldPlate[];
  lines: WorldPoint[][];
  arrows: FieldArrow[];
  neutral: WorldPoint[];
  /** The part of the question this picture answers: "a" titles it "(a)". */
  part?: string;
};

// The server's limits (`schemas/field_lines.py`).
const MAX_CHARGES = 3;
const MAX_PLATES = 2;
const MAX_LINES = 64;
const LINE_POINTS = [2, 160] as const;
const MAX_POINTS = 2400;
const MAX_NEUTRAL = 3;
const MAX_LABEL = 16;
const PART = /^[a-h]$/;

function sign(value: unknown): 1 | -1 {
  if (value !== 1 && value !== -1) refuse();
  return value;
}

function parseCharge(raw: unknown): FieldCharge {
  const row = requireRecord(raw);
  const radius = requireNumber(row.radius);
  if (!(radius > 0 && radius <= 1)) refuse();
  return {
    at: requirePoint(row.at),
    sign: sign(row.sign),
    radius,
    label: optionalText(row.label, MAX_LABEL),
  };
}

function parsePlate(raw: unknown): FieldPlate {
  const row = requireRecord(raw);
  const start = requirePoint(row.start);
  const end = requirePoint(row.end);
  if (start.x === end.x && start.y === end.y) refuse();
  return { start, end, sign: sign(row.sign) };
}

function parseArrow(raw: unknown): FieldArrow {
  const row = requireRecord(raw);
  const dx = requireNumber(row.dx);
  const dy = requireNumber(row.dy);
  if (dx === 0 && dy === 0) refuse();
  return { at: requirePoint(row.at), dx, dy };
}

/**
 * Read the `field` object of a fence, or null when it is malformed — as the
 * server model would: both charges and plates or neither, a line of one point,
 * too many points to draw, a direction of nothing.
 */
export function parseFieldSpec(raw: unknown): FieldSpec | null {
  return guard(() => {
    const row = requireRecord(raw);
    const charges = optionalList(row.charges, MAX_CHARGES).map(parseCharge);
    const plates = optionalList(row.plates, MAX_PLATES).map(parsePlate);
    if ((charges.length > 0) === (plates.length > 0)) refuse();
    if (!Array.isArray(row.lines) || row.lines.length < 1 || row.lines.length > MAX_LINES) refuse();
    let total = 0;
    const lines = row.lines.map((line) => {
      if (!Array.isArray(line) || line.length < LINE_POINTS[0] || line.length > LINE_POINTS[1]) refuse();
      total += line.length;
      return line.map(requirePoint);
    });
    if (total > MAX_POINTS) refuse();
    const arrows = optionalList(row.arrows, MAX_LINES).map(parseArrow);
    const neutral = optionalList(row.neutral, MAX_NEUTRAL).map(requirePoint);
    let part: string | undefined;
    if (row.part !== undefined && row.part !== null) {
      if (typeof row.part !== "string" || !PART.test(row.part)) refuse();
      part = row.part;
    }
    return { charges, plates, lines, arrows, neutral, part };
  });
}

// --- layout ---------------------------------------------------------------------

export type FieldScene = {
  lines: ScreenPoint[][];
  arrows: { tip: ScreenPoint; ux: number; uy: number }[];
  charges: { centre: ScreenPoint; r: number; sign: 1 | -1; label?: string }[];
  plates: { from: ScreenPoint; to: ScreenPoint; sign: 1 | -1; marks: ScreenPoint[] }[];
  neutral: ScreenPoint[];
};

/** A plate's sign is written this often along it, in pixels. */
const PLATE_MARK_EVERY = 28;
/** The arrowhead's tip sits this far past the server's point, so the head straddles it. */
const HEAD_AHEAD = 4;

/**
 * The scene in canvas pixels. One scale for both axes (`worldTransform`), so
 * a line leaves a charge at the angle the server traced; y grows up in the
 * world and down on screen, so a direction's y is flipped.
 */
export function layoutFieldScene(
  field: FieldSpec,
  bounds: WorldBounds,
  width: number,
  height: number,
): FieldScene {
  const t = worldTransform(bounds, width, height);
  const screen = (point: WorldPoint) => toScreen(point.x, point.y, t);
  return {
    lines: field.lines.map((line) => line.map(screen)),
    arrows: field.arrows.map((arrow) => {
      const length = Math.hypot(arrow.dx, arrow.dy);
      const ux = arrow.dx / length;
      const uy = -arrow.dy / length;
      const at = screen(arrow.at);
      return { tip: { px: at.px + ux * HEAD_AHEAD, py: at.py + uy * HEAD_AHEAD }, ux, uy };
    }),
    charges: field.charges.map((charge) => ({
      centre: screen(charge.at),
      r: charge.radius * t.scale,
      sign: charge.sign,
      label: charge.label,
    })),
    plates: field.plates.map((plate) => {
      const from = screen(plate.start);
      const to = screen(plate.end);
      const length = Math.hypot(to.px - from.px, to.py - from.py);
      const count = Math.max(2, Math.floor(length / PLATE_MARK_EVERY));
      const marks = Array.from({ length: count }, (_, index) => {
        const f = (index + 0.5) / count;
        return { px: from.px + (to.px - from.px) * f, py: from.py + (to.py - from.py) * f };
      });
      return { from, to, sign: plate.sign, marks };
    }),
    neutral: field.neutral.map(screen),
  };
}

/** The diagram's title: "(a) Electric Field" for a part's picture. */
export function fieldTitle(title: string, part: string | undefined): string {
  return part ? `(${part}) ${title}` : title;
}

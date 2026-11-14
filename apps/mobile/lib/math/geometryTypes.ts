export type RectangleSpec = {
  type: "rectangle" | "square";
  width: number;
  height: number;
  unit?: string;
  show_diagonal?: boolean;
  show_angle?: boolean;
  show_area?: boolean;
  show_perimeter?: boolean;
  /** School-diagram congruence ticks on equal sides (default on). */
  show_ticks?: boolean;
  diagonal?: number;
  angle_deg?: number;
  area?: number;
  perimeter?: number;
  labels?: Record<string, string>;
};

export type TriangleSpec = {
  type: "triangle";
  base: number;
  height: number;
  unit?: string;
  show_labels?: boolean;
  /** Congruence tick marks on equal legs (default on). */
  show_ticks?: boolean;
  /** Dashed altitude from apex to base (default on — already the height line). */
  show_altitude?: boolean;
  /** Interior vertex degrees (default on). */
  show_angle?: boolean;
  area?: number;
  labels?: Record<string, string>;
};

export type RightTriangleSpec = {
  type: "right_triangle";
  base: number;
  height: number;
  unit?: string;
  show_labels?: boolean;
  show_hypotenuse?: boolean;
  /** Interior vertex degrees, not only the 90° square (default on). */
  show_angle?: boolean;
  hypotenuse?: number;
  area?: number;
  labels?: Record<string, string>;
};

export type CircleSpec = {
  type: "circle";
  radius: number;
  unit?: string;
  show_labels?: boolean;
  show_diameter?: boolean;
  show_area?: boolean;
  show_circumference?: boolean;
  diameter?: number;
  area?: number;
  circumference?: number;
  labels?: Record<string, string>;
};

export type TriangleSidesSpec = {
  type: "triangle_sides";
  a: number;
  b: number;
  c: number;
  relative_lengths?: boolean;
  unit?: string;
  show_labels?: boolean;
  /** Congruence ticks on equal sides (default on when any sides match). */
  show_ticks?: boolean;
  /** Altitude from the apex (opp. side a) to side a (default on). */
  show_altitude?: boolean;
  /** Median from the apex to the midpoint of side a (default off; on for isosceles). */
  show_median?: boolean;
  show_angle?: boolean;
  area?: number;
  labels?: Record<string, string>;
};

export type TrapezoidSpec = {
  type: "trapezoid";
  top: number;
  bottom: number;
  height: number;
  unit?: string;
  show_labels?: boolean;
  show_angle?: boolean;
  area?: number;
  labels?: Record<string, string>;
};

export type ParallelogramSpec = {
  type: "parallelogram";
  base: number;
  height: number;
  side: number;
  unit?: string;
  show_labels?: boolean;
  show_angle?: boolean;
  show_perimeter?: boolean;
  area?: number;
  perimeter?: number;
  labels?: Record<string, string>;
};

export type SectorSpec = {
  type: "sector";
  radius: number;
  angle_deg: number;
  unit?: string;
  show_labels?: boolean;
  arc_length?: number;
  area?: number;
  /** The arc and both radii (a quarter circle's perimeter), when that was asked. */
  perimeter?: number;
  labels?: Record<string, string>;
};

/** A point of a server-drawn figure, in the question's units; `show` draws its name. */
export type FigurePoint = { name: string; x: number; y: number; show?: boolean; dot?: boolean };

/** A side or line between two named points: a label, dashes, equal-length or parallel marks. */
export type FigureSegment = {
  a: string;
  b: string;
  label?: string;
  dashed?: boolean;
  ticks?: number;
  arrows?: number;
  /** Where along the segment its label sits (0.5 its middle). */
  label_at?: number;
};

/** An arc of an axis-aligned ellipse about a point, degrees counterclockwise (a circle: rx = ry). */
export type FigureArc = {
  center: string;
  rx: number;
  ry: number;
  start: number;
  end: number;
  dashed?: boolean;
};

/** The angle at `at` between the rays to `a` and `b` (under 180°), labelled or a right angle. */
export type FigureAngle = { at: string; a: string; b: string; label?: string; right?: boolean };

/**
 * A drawing the server worked out from the question's own values (`math/figure`): any
 * plane figure, lines and angles, circle parts, a solid or its net. The phone fits it to
 * the card and places the labels; it never computes a coordinate.
 */
export type FigureSpec = {
  type: "figure";
  shape: string;
  points: FigurePoint[];
  segments: FigureSegment[];
  arcs: FigureArc[];
  angles: FigureAngle[];
  faces: string[][];
};

export type GeometrySpec =
  | FigureSpec
  | RectangleSpec
  | TriangleSpec
  | RightTriangleSpec
  | CircleSpec
  | TriangleSidesSpec
  | TrapezoidSpec
  | ParallelogramSpec
  | SectorSpec;

const GEOMETRY_KIND_SET: Record<GeometrySpec["type"], true> = {
  figure: true,
  rectangle: true,
  square: true,
  triangle: true,
  right_triangle: true,
  circle: true,
  triangle_sides: true,
  trapezoid: true,
  parallelogram: true,
  sector: true,
};

/** Every figure this build draws; a fence naming another is refused as an unknown kind. */
export const GEOMETRY_KINDS = Object.keys(GEOMETRY_KIND_SET);

/** Match backend `RectangleGeometryInput` / triangle inputs (`le=1_000_000`). */
export const MAX_GEOMETRY_DIMENSION = 1_000_000;

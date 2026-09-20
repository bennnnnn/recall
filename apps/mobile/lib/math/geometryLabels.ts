import { formatAngleDeg } from "@/lib/math/geometryAngles";
import {
  type CircleSpec,
  type ParallelogramSpec,
  type RectangleSpec,
  type RightTriangleSpec,
  type SectorSpec,
  type TrapezoidSpec,
  type TriangleSidesSpec,
  type TriangleSpec,
} from "@/lib/math/geometryTypes";

export function computeRectangleLabels(spec: RectangleSpec): Record<string, string> {
  const unit = spec.unit ?? "cm";
  const diagonal =
    spec.diagonal ?? Math.sqrt(spec.width * spec.width + spec.height * spec.height);
  const angle = spec.angle_deg ?? (Math.atan2(spec.height, spec.width) * 180) / Math.PI;
  const area = spec.area ?? spec.width * spec.height;
  const perimeter = spec.perimeter ?? 2 * (spec.width + spec.height);
  const sideLabel = spec.labels?.side ?? `${spec.width} ${unit}`;
  return {
    width: spec.labels?.width ?? `${spec.width} ${unit}`,
    height: spec.labels?.height ?? `${spec.height} ${unit}`,
    side: sideLabel,
    diagonal: spec.labels?.diagonal ?? `${diagonal.toFixed(2)} ${unit}`,
    angle: spec.labels?.angle ?? `${angle.toFixed(1)}°`,
    area: spec.labels?.area ?? `${area % 1 === 0 ? area : area.toFixed(1)} ${unit}²`,
    perimeter: spec.labels?.perimeter ?? `${perimeter % 1 === 0 ? perimeter : perimeter.toFixed(1)} ${unit}`,
  };
}

export function computeTriangleLabels(spec: TriangleSpec): Record<string, string> {
  const unit = spec.unit ?? "cm";
  const area = spec.area ?? 0.5 * spec.base * spec.height;
  return {
    base: spec.labels?.base ?? `${spec.base} ${unit}`,
    height: spec.labels?.height ?? `${spec.height} ${unit}`,
    area: spec.labels?.area ?? `${area % 1 === 0 ? area : area.toFixed(1)} ${unit}²`,
  };
}

export function computeRightTriangleLabels(spec: RightTriangleSpec): Record<string, string> {
  const unit = spec.unit ?? "cm";
  const area = spec.area ?? 0.5 * spec.base * spec.height;
  const hypotenuse = spec.hypotenuse ?? Math.sqrt(spec.base * spec.base + spec.height * spec.height);
  const angleAtBase = (Math.atan2(spec.height, spec.base) * 180) / Math.PI;
  const angleAtHeight = (Math.atan2(spec.base, spec.height) * 180) / Math.PI;
  return {
    base: spec.labels?.base ?? `${spec.base} ${unit}`,
    height: spec.labels?.height ?? `${spec.height} ${unit}`,
    hypotenuse: spec.labels?.hypotenuse ?? `${hypotenuse % 1 === 0 ? hypotenuse : hypotenuse.toFixed(2)} ${unit}`,
    area: spec.labels?.area ?? `${area % 1 === 0 ? area : area.toFixed(1)} ${unit}²`,
    angle: spec.labels?.angle ?? "90°",
    angle_at_base: spec.labels?.angle_at_base ?? formatAngleDeg(angleAtBase),
    angle_at_height: spec.labels?.angle_at_height ?? formatAngleDeg(angleAtHeight),
  };
}

export function computeCircleLabels(spec: CircleSpec): Record<string, string> {
  const unit = spec.unit ?? "cm";
  const diameter = spec.diameter ?? spec.radius * 2;
  const area = spec.area ?? Math.PI * spec.radius * spec.radius;
  const circumference = spec.circumference ?? 2 * Math.PI * spec.radius;
  return {
    radius: spec.labels?.radius ?? `${spec.radius} ${unit}`,
    diameter: spec.labels?.diameter ?? `${diameter % 1 === 0 ? diameter : diameter.toFixed(2)} ${unit}`,
    area: spec.labels?.area ?? `${area.toFixed(2)} ${unit}²`,
    circumference: spec.labels?.circumference ?? `${circumference.toFixed(2)} ${unit}`,
  };
}

export function computeTriangleSidesLabels(spec: TriangleSidesSpec): Record<string, string> {
  if (spec.relative_lengths) {
    return { a: String(spec.a), b: String(spec.b), c: String(spec.c), area: "" };
  }
  const unit = spec.unit ?? "cm";
  const s = (spec.a + spec.b + spec.c) / 2;
  const area = spec.area ?? Math.sqrt(s * (s - spec.a) * (s - spec.b) * (s - spec.c));
  return {
    a: spec.labels?.a ?? `${spec.a} ${unit}`,
    b: spec.labels?.b ?? `${spec.b} ${unit}`,
    c: spec.labels?.c ?? `${spec.c} ${unit}`,
    area: spec.labels?.area ?? `${area % 1 === 0 ? area : area.toFixed(2)} ${unit}²`,
  };
}

export function computeTrapezoidLabels(spec: TrapezoidSpec): Record<string, string> {
  const unit = spec.unit ?? "cm";
  const area = spec.area ?? ((spec.top + spec.bottom) / 2) * spec.height;
  return {
    top: spec.labels?.top ?? `${spec.top} ${unit}`,
    bottom: spec.labels?.bottom ?? `${spec.bottom} ${unit}`,
    height: spec.labels?.height ?? `${spec.height} ${unit}`,
    area: spec.labels?.area ?? `${area % 1 === 0 ? area : area.toFixed(1)} ${unit}²`,
  };
}

export function computeParallelogramLabels(spec: ParallelogramSpec): Record<string, string> {
  const unit = spec.unit ?? "cm";
  const area = spec.area ?? spec.base * spec.height;
  const perimeter = spec.perimeter ?? 2 * (spec.base + spec.side);
  return {
    base: spec.labels?.base ?? `${spec.base} ${unit}`,
    height: spec.labels?.height ?? `${spec.height} ${unit}`,
    side: spec.labels?.side ?? `${spec.side} ${unit}`,
    area: spec.labels?.area ?? `${area % 1 === 0 ? area : area.toFixed(1)} ${unit}²`,
    perimeter: spec.labels?.perimeter ?? `${perimeter % 1 === 0 ? perimeter : perimeter.toFixed(1)} ${unit}`,
  };
}

export function computeSectorLabels(spec: SectorSpec): Record<string, string> {
  const unit = spec.unit ?? "cm";
  const rad = (spec.angle_deg * Math.PI) / 180;
  const arcLength = spec.arc_length ?? spec.radius * rad;
  const area = spec.area ?? 0.5 * spec.radius * spec.radius * rad;
  return {
    radius: spec.labels?.radius ?? `${spec.radius} ${unit}`,
    angle: spec.labels?.angle ?? `${spec.angle_deg}°`,
    arc_length: spec.labels?.arc_length ?? `${arcLength.toFixed(2)} ${unit}`,
    area: spec.labels?.area ?? `${area.toFixed(2)} ${unit}²`,
  };
}

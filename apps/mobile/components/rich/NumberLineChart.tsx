import Svg, { Circle, Line, Polygon, Text as SvgText } from "react-native-svg";

import {
  formatInequalityExpr,
  GraphSpec,
  numberLineBounds,
  numberLineTicks,
  NumberLineInterval,
} from "@/lib/graphBlock";

type Props = {
  spec: GraphSpec;
  width: number;
  color: string;
  axisColor: string;
  labelColor: string;
  holeFill: string;
};

const HEIGHT = 96;
const PAD = 28;
const RADIUS = 7;
const ARROW = 9;
const RAY_INSET = RADIUS + 2;

function formatTick(n: number): string {
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

function mapX(x: number, xMin: number, xMax: number, width: number): number {
  return PAD + ((x - xMin) / (xMax - xMin || 1)) * (width - PAD * 2);
}

function arrowPoints(tipX: number, y: number, dir: "left" | "right"): string {
  const dx = dir === "right" ? -ARROW : ARROW;
  return `${tipX},${y} ${tipX + dx},${y - ARROW * 0.7} ${tipX + dx},${y + ARROW * 0.7}`;
}

function raySpan(
  iv: NumberLineInterval,
  xMin: number,
  xMax: number,
  width: number,
): { x1: number; x2: number } | null {
  if (iv.start != null && iv.end != null && iv.start === iv.end) return null;
  const leftPx = PAD;
  const rightPx = width - PAD;
  let x1 = iv.start == null ? leftPx : mapX(iv.start, xMin, xMax, width);
  let x2 = iv.end == null ? rightPx : mapX(iv.end, xMin, xMax, width);
  if (iv.start != null) x1 += RAY_INSET;
  if (iv.end != null) x2 -= RAY_INSET;
  if (x2 <= x1) return null;
  return { x1, x2 };
}

export function NumberLineChart({
  spec,
  width,
  color,
  axisColor,
  labelColor,
  holeFill,
}: Props) {
  const intervals = spec.intervals ?? [];
  const { xMin, xMax } = numberLineBounds(intervals);
  const y = HEIGHT / 2;
  const leftPx = PAD;
  const rightPx = width - PAD;
  const tickVals = numberLineTicks(xMin, xMax);
  const rayLeft = intervals.some((iv) => iv.start == null);
  const rayRight = intervals.some((iv) => iv.end == null);

  return (
    <Svg width={width} height={HEIGHT} accessibilityLabel={formatInequalityExpr(spec.expr)}>
      <Line
        x1={leftPx}
        y1={y}
        x2={rightPx}
        y2={y}
        stroke={axisColor}
        strokeWidth={1.5}
      />
      <Polygon points={arrowPoints(leftPx, y, "left")} fill={axisColor} />
      {rayRight ? null : (
        <Polygon points={arrowPoints(rightPx, y, "right")} fill={axisColor} />
      )}
      {tickVals.map((n) => {
        const px = mapX(n, xMin, xMax, width);
        return (
          <Line
            key={`t-${n}`}
            x1={px}
            y1={y - 6}
            x2={px}
            y2={y + 6}
            stroke={axisColor}
            strokeWidth={1.5}
          />
        );
      })}
      {intervals.map((iv, i) => {
        const span = raySpan(iv, xMin, xMax, width);
        if (!span) return null;
        return (
          <Line
            key={`seg-${i}`}
            x1={span.x1}
            y1={y}
            x2={span.x2}
            y2={y}
            stroke={color}
            strokeWidth={3.5}
            strokeLinecap="butt"
          />
        );
      })}
      {rayRight ? (
        <Polygon points={arrowPoints(rightPx, y, "right")} fill={color} />
      ) : null}
      {rayLeft ? (
        <Polygon points={arrowPoints(leftPx, y, "left")} fill={color} />
      ) : null}
      {intervals.map((iv, i) => {
        const nodes: { px: number; filled: boolean; key: string }[] = [];
        if (iv.start != null) {
          nodes.push({
            px: mapX(iv.start, xMin, xMax, width),
            filled: iv.start_inclusive,
            key: `s-${i}`,
          });
        }
        if (iv.end != null && iv.end !== iv.start) {
          nodes.push({
            px: mapX(iv.end, xMin, xMax, width),
            filled: iv.end_inclusive,
            key: `e-${i}`,
          });
        }
        if (iv.end != null && iv.end === iv.start) {
          nodes[0] = {
            px: mapX(iv.start as number, xMin, xMax, width),
            filled: iv.start_inclusive && iv.end_inclusive,
            key: `p-${i}`,
          };
        }
        return nodes.map((node) => (
          <Circle
            key={node.key}
            cx={node.px}
            cy={y}
            r={RADIUS}
            fill={node.filled ? color : holeFill}
            stroke={color}
            strokeWidth={2.5}
          />
        ));
      })}
      {tickVals.map((n) => (
        <SvgText
          key={`l-${n}`}
          x={mapX(n, xMin, xMax, width)}
          y={y + 22}
          fill={labelColor}
          fontSize={12}
          textAnchor="middle"
        >
          {formatTick(n)}
        </SvgText>
      ))}
    </Svg>
  );
}

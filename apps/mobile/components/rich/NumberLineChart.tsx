import Svg, { Circle, Line, Polygon, Text as SvgText } from "react-native-svg";

import {
  formatInequalityExpr,
  GraphSpec,
  numberLineBounds,
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
const RADIUS = 6;
const ARROW = 8;

function formatTick(n: number): string {
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

function mapX(x: number, xMin: number, xMax: number, width: number): number {
  return PAD + ((x - xMin) / (xMax - xMin || 1)) * (width - PAD * 2);
}

function ticksFor(intervals: NumberLineInterval[], xMin: number, xMax: number): number[] {
  const raw = [0];
  for (const iv of intervals) {
    if (iv.start != null) raw.push(iv.start);
    if (iv.end != null) raw.push(iv.end);
  }
  const seen = new Set<number>();
  const out: number[] = [];
  for (const n of raw) {
    if (n < xMin || n > xMax) continue;
    const key = Math.round(n * 1e6);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(n);
  }
  return out.sort((a, b) => a - b);
}

function arrowPoints(tipX: number, y: number, dir: "left" | "right"): string {
  const dx = dir === "right" ? -ARROW : ARROW;
  return `${tipX},${y} ${tipX + dx},${y - ARROW * 0.7} ${tipX + dx},${y + ARROW * 0.7}`;
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
  const tickVals = ticksFor(intervals, xMin, xMax);

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
        const startPx = iv.start == null ? leftPx : mapX(iv.start, xMin, xMax, width);
        const endPx = iv.end == null ? rightPx : mapX(iv.end, xMin, xMax, width);
        const isPoint = iv.start != null && iv.end != null && iv.start === iv.end;
        return (
          <Line
            key={`seg-${i}`}
            x1={startPx}
            y1={y}
            x2={isPoint ? startPx : endPx}
            y2={y}
            stroke={color}
            strokeWidth={isPoint ? 0 : 3.5}
            strokeLinecap="round"
          />
        );
      })}
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
      {intervals.some((iv) => iv.end == null) ? (
        <Polygon points={arrowPoints(rightPx, y, "right")} fill={color} />
      ) : null}
      {intervals.some((iv) => iv.start == null) ? (
        <Polygon points={arrowPoints(leftPx, y, "left")} fill={color} />
      ) : null}
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
      <SvgText
        x={rightPx}
        y={y - 12}
        fill={labelColor}
        fontSize={12}
        textAnchor="end"
      >
        {spec.variable ?? "x"}
      </SvgText>
    </Svg>
  );
}

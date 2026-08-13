import Svg, { Line, Rect, Text as SvgText } from "react-native-svg";

import {
  formatInequalityExpr,
  GraphSpec,
  mapGraphPoint,
  numberLineBounds,
  numberLineTicks,
  NumberLineInterval,
} from "@/lib/graphBlock";

type Props = {
  spec: GraphSpec;
  width: number;
  height: number;
  color: string;
  axisColor: string;
  labelColor: string;
};

const PAD = 28;
const Y_MIN = -5;
const Y_MAX = 5;

function formatTick(n: number): string {
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

function shadeRect(
  iv: NumberLineInterval,
  bounds: { xMin: number; xMax: number; yMin: number; yMax: number },
  width: number,
  height: number,
): { x: number; y: number; w: number; h: number } | null {
  const x1 =
    iv.start == null
      ? mapGraphPoint(bounds.xMin, 0, bounds, width, height, PAD).px
      : mapGraphPoint(iv.start, 0, bounds, width, height, PAD).px;
  const x2 =
    iv.end == null
      ? mapGraphPoint(bounds.xMax, 0, bounds, width, height, PAD).px
      : mapGraphPoint(iv.end, 0, bounds, width, height, PAD).px;
  const top = mapGraphPoint(0, bounds.yMax, bounds, width, height, PAD).py;
  const bot = mapGraphPoint(0, bounds.yMin, bounds, width, height, PAD).py;
  const left = Math.min(x1, x2);
  const right = Math.max(x1, x2);
  if (right - left < 1) return null;
  return { x: left, y: top, w: right - left, h: bot - top };
}

export function InequalityRegionChart({
  spec,
  width,
  height,
  color,
  axisColor,
  labelColor,
}: Props) {
  const intervals = spec.intervals ?? [];
  const xBounds = numberLineBounds(intervals);
  const bounds = {
    xMin: xBounds.xMin,
    xMax: xBounds.xMax,
    yMin: Y_MIN,
    yMax: Y_MAX,
  };
  const origin = mapGraphPoint(0, 0, bounds, width, height, PAD);
  const xTicks = numberLineTicks(bounds.xMin, bounds.xMax);
  const yTicks = [-4, -2, 2, 4];

  return (
    <Svg
      width={width}
      height={height}
      accessibilityLabel={formatInequalityExpr(spec.expr)}
    >
      {intervals.map((iv, i) => {
        const r = shadeRect(iv, bounds, width, height);
        if (!r) return null;
        return (
          <Rect
            key={`shade-${i}`}
            x={r.x}
            y={r.y}
            width={r.w}
            height={r.h}
            fill={color}
            fillOpacity={0.22}
          />
        );
      })}
      <Line
        x1={origin.px}
        y1={PAD}
        x2={origin.px}
        y2={height - PAD}
        stroke={axisColor}
        strokeWidth={1}
      />
      <Line
        x1={PAD}
        y1={origin.py}
        x2={width - PAD}
        y2={origin.py}
        stroke={axisColor}
        strokeWidth={1}
      />
      {intervals.map((iv, i) => {
        const cuts: { x: number; dashed: boolean; key: string }[] = [];
        if (iv.start != null) {
          cuts.push({
            x: mapGraphPoint(iv.start, 0, bounds, width, height, PAD).px,
            dashed: !iv.start_inclusive,
            key: `b-s-${i}`,
          });
        }
        if (iv.end != null && iv.end !== iv.start) {
          cuts.push({
            x: mapGraphPoint(iv.end, 0, bounds, width, height, PAD).px,
            dashed: !iv.end_inclusive,
            key: `b-e-${i}`,
          });
        }
        return cuts.map((cut) => (
          <Line
            key={cut.key}
            x1={cut.x}
            y1={PAD}
            x2={cut.x}
            y2={height - PAD}
            stroke={color}
            strokeWidth={2}
            strokeDasharray={cut.dashed ? "6 4" : undefined}
          />
        ));
      })}
      {xTicks.map((n) => {
        if (n === 0) return null;
        const { px } = mapGraphPoint(n, 0, bounds, width, height, PAD);
        return (
          <SvgText
            key={`xt-${n}`}
            x={px}
            y={origin.py + 16}
            fill={labelColor}
            fontSize={11}
            textAnchor="middle"
          >
            {formatTick(n)}
          </SvgText>
        );
      })}
      {yTicks.map((n) => {
        const { py } = mapGraphPoint(0, n, bounds, width, height, PAD);
        return (
          <SvgText
            key={`yt-${n}`}
            x={origin.px - 6}
            y={py + 4}
            fill={labelColor}
            fontSize={11}
            textAnchor="end"
          >
            {formatTick(n)}
          </SvgText>
        );
      })}
      <SvgText
        x={width - PAD}
        y={origin.py - 6}
        fill={labelColor}
        fontSize={11}
        textAnchor="end"
      >
        {spec.variable ?? "x"}
      </SvgText>
      <SvgText
        x={origin.px + 6}
        y={PAD + 4}
        fill={labelColor}
        fontSize={11}
      >
        y
      </SvgText>
    </Svg>
  );
}

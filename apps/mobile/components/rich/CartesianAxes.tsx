import { ClipPath, Defs, Line, Rect, Text as SvgText } from "react-native-svg";

import {
  formatAxisNumber,
  graphAxisTicks,
  mapGraphPoint,
} from "@/lib/graphBlock";

type Bounds = {
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
};

type Props = {
  width: number;
  height: number;
  pad: number;
  bounds: Bounds;
  clipId: string;
  axisColor: string;
  labelColor: string;
  gridColor: string;
  xName: string;
  yName: string;
};

const TICK_FONT = 11;

/** Grid, axes, and even tick labels for a function/trajectory plot. */
export function CartesianAxes({
  width,
  height,
  pad,
  bounds,
  clipId,
  axisColor,
  labelColor,
  gridColor,
  xName,
  yName,
}: Props) {
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  const origin = mapGraphPoint(0, 0, bounds, width, height);
  const yAxisX = origin.px;
  const xAxisY = origin.py;
  const xTicks = graphAxisTicks(bounds.xMin, bounds.xMax);
  const yTicks = graphAxisTicks(bounds.yMin, bounds.yMax);

  return (
    <>
      <Defs>
        <ClipPath id={clipId}>
          <Rect x={pad} y={pad} width={innerW} height={innerH} />
        </ClipPath>
      </Defs>
      {xTicks.map((n) => {
        if (Math.abs(n) < 1e-9) return null;
        const { px } = mapGraphPoint(n, 0, bounds, width, height);
        return (
          <Line
            key={`gx-${n}`}
            x1={px}
            y1={pad}
            x2={px}
            y2={height - pad}
            stroke={gridColor}
            strokeWidth={1}
          />
        );
      })}
      {yTicks.map((n) => {
        if (Math.abs(n) < 1e-9) return null;
        const { py } = mapGraphPoint(0, n, bounds, width, height);
        return (
          <Line
            key={`gy-${n}`}
            x1={pad}
            y1={py}
            x2={width - pad}
            y2={py}
            stroke={gridColor}
            strokeWidth={1}
          />
        );
      })}
      <Line
        x1={yAxisX}
        y1={pad}
        x2={yAxisX}
        y2={height - pad}
        stroke={axisColor}
        strokeWidth={1.25}
      />
      <Line
        x1={pad}
        y1={xAxisY}
        x2={width - pad}
        y2={xAxisY}
        stroke={axisColor}
        strokeWidth={1.25}
      />
      {xTicks.map((n) => {
        if (Math.abs(n) < 1e-9) return null;
        const { px } = mapGraphPoint(n, 0, bounds, width, height);
        return (
          <SvgText
            key={`lx-${n}`}
            x={px}
            y={xAxisY + 16}
            fill={labelColor}
            fontSize={TICK_FONT}
            textAnchor="middle"
          >
            {formatAxisNumber(n)}
          </SvgText>
        );
      })}
      {yTicks.map((n) => {
        if (Math.abs(n) < 1e-9) return null;
        const { py } = mapGraphPoint(0, n, bounds, width, height);
        if (py < pad + 12) return null;
        return (
          <SvgText
            key={`ly-${n}`}
            x={Math.max(4, yAxisX - 6)}
            y={py + 4}
            fill={labelColor}
            fontSize={TICK_FONT}
            textAnchor="end"
          >
            {formatAxisNumber(n)}
          </SvgText>
        );
      })}
      <SvgText
        x={width - pad}
        y={xAxisY - 6}
        fill={labelColor}
        fontSize={TICK_FONT}
        textAnchor="end"
      >
        {xName}
      </SvgText>
      <SvgText
        x={yAxisX}
        y={pad - 2}
        fill={labelColor}
        fontSize={TICK_FONT}
        textAnchor="middle"
      >
        {yName}
      </SvgText>
    </>
  );
}

import { useMemo } from "react";
import Svg, { Circle, Line, Polygon, Polyline, Text as SvgText } from "react-native-svg";

import { figureWidth } from "@/components/rich/figure";
import { figureLayout, type FigureSpec } from "@/lib/math/geometryBlock";
import { type Theme } from "@/lib/theme";
import { Weight } from "@/lib/type";

type Px = { x: number; y: number };

const list = (points: Px[]) => points.map((p) => `${p.x},${p.y}`).join(" ");

/** A figure the server drew from the question's values: its sides, arcs, marks and labels. */
export function FigureDiagram({
  spec,
  screenWidth,
  theme,
}: {
  spec: FigureSpec;
  screenWidth: number;
  theme: Theme;
}) {
  const layout = useMemo(() => figureLayout(spec, figureWidth(screenWidth)), [spec, screenWidth]);
  return (
    <Svg width={layout.width} height={layout.height} testID="geometry-figure">
      {layout.faces.map((face, i) => (
        <Polygon key={`face-${i}`} points={list(face)} fill={theme.contentSurface} stroke="none" />
      ))}
      {layout.arcs.map((arc, i) => (
        <Polyline
          key={`arc-${i}`}
          points={list(arc.points)}
          fill="none"
          stroke={theme.primary}
          strokeWidth={2}
          strokeDasharray={arc.dashed ? "5,4" : undefined}
        />
      ))}
      {layout.lines.map((line, i) => (
        <Line
          key={`line-${i}`}
          x1={line.from.x}
          y1={line.from.y}
          x2={line.to.x}
          y2={line.to.y}
          stroke={line.dashed ? theme.accent : theme.primary}
          strokeWidth={line.dashed ? 1.5 : 2}
          strokeDasharray={line.dashed ? "5,4" : undefined}
          strokeLinecap="round"
        />
      ))}
      {layout.marks.map(([from, to], i) => (
        <Line
          key={`mark-${i}`}
          x1={from.x}
          y1={from.y}
          x2={to.x}
          y2={to.y}
          stroke={theme.primary}
          strokeWidth={1.5}
        />
      ))}
      {layout.angleArcs.map((path, i) => (
        <Polyline
          key={`angle-${i}`}
          points={list(path)}
          fill="none"
          stroke={theme.textSecondary}
          strokeWidth={1.5}
        />
      ))}
      {layout.dots.map((dot, i) => (
        <Circle key={`dot-${i}`} cx={dot.x} cy={dot.y} r={3} fill={theme.primary} />
      ))}
      {layout.labels.map((label, i) => (
        <SvgText
          key={`label-${i}`}
          x={label.x}
          y={label.y}
          fill={theme.text}
          fontSize={12}
          {...Weight.semibold}
          textAnchor={label.anchor}
        >
          {label.text}
        </SvgText>
      ))}
    </Svg>
  );
}

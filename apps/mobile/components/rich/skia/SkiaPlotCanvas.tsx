/**
 * A server-drawn plot in Skia: the same layout `PlotGraphCard` draws in SVG
 * (`plotLayout`), with the function plot's grid, axes and tick labels
 * (`computeChrome`). Static: the plot has no pan or zoom, so nothing here is
 * a worklet. Loaded lazily and only when Skia is linked.
 */
import { useMemo } from "react";
import {
  Canvas,
  Circle,
  DashPathEffect,
  Group,
  Path,
  Skia,
  Text as SkiaText,
} from "@shopify/react-native-skia";

import { GRAPH_AXIS_PAD } from "@/components/rich/GraphCanvas";
import { GRAPH_TICK_FONT_SIZE } from "@/components/rich/graphPaint";
import {
  MIRROR_DASH,
  PLOT_DASH,
  PLOT_HEIGHT,
  PLOT_TURN,
  plotColor,
  plotStroke,
  REGION_OPACITY,
} from "@/components/rich/plotPaint";
import { useFigureFont } from "@/components/rich/skia/figureFont";
import { computeChrome, MONO_CHAR_PX } from "@/components/rich/skia/graphPaths";
import { HaloText } from "@/components/rich/skia/HaloText";
import { type PlotGraph, type PlotLayout } from "@/lib/math/plotGraph";
import { type Theme } from "@/lib/theme";

type Px = { px: number; py: number };

function pathOf(points: Px[], closed: boolean) {
  const path = Skia.PathBuilder.Make();
  points.forEach(({ px, py }, i) => (i ? path.lineTo(px, py) : path.moveTo(px, py)));
  if (closed) path.close();
  return path.detach();
}

export function SkiaPlotCanvas({
  graph,
  layout,
  width,
  theme,
}: {
  graph: PlotGraph;
  layout: PlotLayout;
  width: number;
  theme: Theme;
}) {
  // The system face: it carries the labels' −, √, π, superscripts and the turn arrow.
  const font = useFigureFont(GRAPH_TICK_FONT_SIZE);
  const pad = GRAPH_AXIS_PAD;
  const chrome = useMemo(
    () => computeChrome(layout.bounds, width, PLOT_HEIGHT, pad, font),
    [font, layout.bounds, pad, width],
  );
  const curves = useMemo(
    () => layout.curves.flatMap((curve) => curve.paths.map((p) => ({ color: curve.color, path: pathOf(p, false) }))),
    [layout.curves],
  );
  const regions = useMemo(
    () => layout.regions.map((region) => ({ ...region, path: pathOf(region.points, true) })),
    [layout.regions],
  );
  const lines = useMemo(
    () => layout.lines.map((line) => ({ ...line, path: pathOf([line.from, line.to], false) })),
    [layout.lines],
  );
  const clip = Skia.XYWHRect(pad, pad, Math.max(0, width - pad * 2), Math.max(0, PLOT_HEIGHT - pad * 2));
  const measure = (text: string) => (font ? font.measureText(text).width : text.length * MONO_CHAR_PX);
  const start = (x: number, text: string, anchor: string) =>
    anchor === "end" ? x - measure(text) : anchor === "middle" ? x - measure(text) / 2 : x;

  return (
    <Canvas style={{ width, height: PLOT_HEIGHT }} testID="plot-graph-skia">
      <Path path={chrome.grid} color={theme.border} style="stroke" strokeWidth={1} />
      <Path path={chrome.axes} color={theme.textSecondary} style="stroke" strokeWidth={1.25} />
      <Group clip={clip}>
        {regions.map((region, i) => (
          <Group key={`region-${i}`}>
            <Path
              path={region.path}
              color={plotColor(theme, region.color)}
              style="fill"
              opacity={REGION_OPACITY[region.kind]}
            />
            {region.kind === "shade" ? null : (
              <Path path={region.path} color={plotColor(theme, region.color)} style="stroke" strokeWidth={1}>
                {region.kind === "mirror" ? <DashPathEffect intervals={MIRROR_DASH} /> : null}
              </Path>
            )}
          </Group>
        ))}
        {curves.map((curve, i) => (
          <Path
            key={`curve-${i}`}
            path={curve.path}
            color={plotColor(theme, curve.color)}
            style="stroke"
            strokeWidth={2.5}
            strokeCap="round"
            strokeJoin="round"
          />
        ))}
        {lines.map((line, i) => {
          const stroke = plotStroke(theme, line.role, line.color);
          const dash = PLOT_DASH[line.role];
          return (
            <Path
              key={`line-${i}`}
              path={line.path}
              color={stroke.color}
              style="stroke"
              strokeWidth={stroke.width}
              strokeCap="round"
            >
              {dash ? <DashPathEffect intervals={dash} /> : null}
            </Path>
          );
        })}
      </Group>
      {layout.dots.map((dot, i) =>
        dot.open ? (
          <Group key={`dot-${i}`}>
            <Circle cx={dot.at.px} cy={dot.at.py} r={4.5} color={theme.elevated} />
            <Circle cx={dot.at.px} cy={dot.at.py} r={4.5} color={plotColor(theme, dot.color)} style="stroke" strokeWidth={2} />
          </Group>
        ) : (
          <Group key={`dot-${i}`}>
            <Circle cx={dot.at.px} cy={dot.at.py} r={5} color={theme.surface} />
            <Circle cx={dot.at.px} cy={dot.at.py} r={4} color={plotColor(theme, dot.color)} />
          </Group>
        ),
      )}
      {font
        ? [...chrome.xLabels, ...chrome.yLabels].map((tick, i) => (
            <SkiaText key={`tick-${i}`} x={tick.px} y={tick.py} text={tick.text} font={font} color={theme.textSecondary} />
          ))
        : null}
      {font ? (
        <>
          <SkiaText
            x={chrome.xNamePos.px - measure(graph.xLabel)}
            y={chrome.xNamePos.py}
            text={graph.xLabel}
            font={font}
            color={theme.textSecondary}
          />
          <SkiaText x={chrome.yNamePos.px} y={chrome.yNamePos.py} text={graph.yLabel} font={font} color={theme.textSecondary} />
          {layout.turns.map((turn, i) => (
            <SkiaText key={`turn-${i}`} x={start(turn.px, PLOT_TURN, "end")} y={turn.py - 6} text={PLOT_TURN} font={font} color={theme.text} />
          ))}
          {layout.labels.map((label, i) => (
            <HaloText
              key={`label-${i}`}
              x={start(label.x, label.text, label.anchor)}
              y={label.y}
              text={label.text}
              font={font}
              color={theme.text}
              halo={theme.surface}
            />
          ))}
        </>
      ) : null}
    </Canvas>
  );
}

/**
 * A server-drawn plot's layers on the Skia function graph, following its view on the UI
 * thread: regions under the curves, lines over them, as `graphLayers.tsx` draws them in SVG.
 */
import { DashPathEffect, Group, Path, Skia, type SkFont, Text as SkiaText } from "@shopify/react-native-skia";
import { useDerivedValue, type SharedValue } from "react-native-reanimated";

import { MIRROR_DASH, PLOT_DASH, PLOT_TURN, plotColor, plotStroke, REGION_OPACITY } from "@/components/rich/plotPaint";
import { mapPointW, type GraphViewW } from "@/lib/math/graphWorklets";
import { type GraphLayers } from "@/lib/math/plotGraph";
import type { Theme } from "@/lib/theme";

type Frame = { bounds: SharedValue<GraphViewW>; width: number; height: number; pad: number };

function usePath(frame: Frame, points: [number, number][], closed: boolean) {
  const { bounds, width, height, pad } = frame;
  return useDerivedValue(() => {
    const path = Skia.PathBuilder.Make();
    points.forEach(([x, y], i) => {
      const { px, py } = mapPointW(x, y, bounds.value, width, height, pad);
      if (i) path.lineTo(px, py);
      else path.moveTo(px, py);
    });
    if (closed) path.close();
    return path.detach();
  });
}

function Region({ region, frame, theme }: { region: GraphLayers["regions"][number]; frame: Frame; theme: Theme }) {
  const path = usePath(frame, region.points, true);
  const color = plotColor(theme, region.color);
  return (
    <Group>
      <Path path={path} color={color} style="fill" opacity={REGION_OPACITY[region.kind]} />
      {region.kind === "shade" ? null : (
        <Path path={path} color={color} style="stroke" strokeWidth={1}>
          {region.kind === "mirror" ? <DashPathEffect intervals={MIRROR_DASH} /> : null}
        </Path>
      )}
    </Group>
  );
}

function PlotLine({ line, frame, theme }: { line: GraphLayers["lines"][number]; frame: Frame; theme: Theme }) {
  const path = usePath(frame, [line.start, line.end], false);
  const stroke = plotStroke(theme, line.role, line.color);
  const dash = PLOT_DASH[line.role];
  return (
    <Path path={path} color={stroke.color} style="stroke" strokeWidth={stroke.width} strokeCap="round">
      {dash ? <DashPathEffect intervals={dash} /> : null}
    </Path>
  );
}

function Turn({ line, frame, font, theme }: { line: GraphLayers["lines"][number]; frame: Frame; font: SkFont; theme: Theme }) {
  const { bounds, width, height, pad } = frame;
  const end = useDerivedValue(() => mapPointW(line.end[0], line.end[1], bounds.value, width, height, pad));
  const advance = font.measureText(PLOT_TURN).width;
  const x = useDerivedValue(() => Math.min(end.value.px, width - pad) - advance);
  const y = useDerivedValue(() => Math.max(end.value.py, pad + 10) - 6);
  return <SkiaText x={x} y={y} text={PLOT_TURN} font={font} color={theme.text} />;
}

export function SkiaGraphLayers({
  layers,
  part,
  frame,
  theme,
  font,
}: {
  layers: GraphLayers;
  part: "under" | "over";
  frame: Frame;
  theme: Theme;
  /** A face with the turn arrow; null while it loads. */
  font: SkFont | null;
}) {
  if (part === "under") {
    return (
      <>
        {layers.regions.map((region, i) => (
          <Region key={`region-${i}`} region={region} frame={frame} theme={theme} />
        ))}
      </>
    );
  }
  return (
    <>
      {layers.lines.map((line, i) => (
        <PlotLine key={`line-${i}`} line={line} frame={frame} theme={theme} />
      ))}
      {font
        ? layers.lines
            .filter((line) => line.role === "axis")
            .map((line, i) => <Turn key={`turn-${i}`} line={line} frame={frame} font={font} theme={theme} />)
        : null}
    </>
  );
}

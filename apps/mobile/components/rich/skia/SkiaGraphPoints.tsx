/**
 * Holes and marked points on the Skia plot, each following the view on the UI thread:
 * a hole is an open ring, a mark (`GraphSpec.marks`) a dot with its label, kept inside
 * the plot (`markLabelW`). The SVG plot draws the same in `graphPoints.tsx`.
 */
import { Circle, Group, type SkFont } from "@shopify/react-native-skia";
import { useDerivedValue, type SharedValue } from "react-native-reanimated";

import {
  MARK_RADIUS,
  markLabelWidth,
  type GraphHoleMarker,
  type GraphMarkMarker,
  type GraphPoints,
} from "@/components/rich/graphPoints";
import { GRAPH_TICK_FONT_SIZE } from "@/components/rich/graphPaint";
import { HaloText } from "@/components/rich/skia/HaloText";
import { mapPointW, markLabelW, type GraphViewW } from "@/lib/math/graphWorklets";
import type { Theme } from "@/lib/theme";

type Frame = { bounds: SharedValue<GraphViewW>; width: number; height: number; pad: number };

function usePlaced({ bounds, width, height, pad }: Frame, point: [number, number]) {
  return useDerivedValue(
    () => mapPointW(point[0], point[1], bounds.value, width, height, pad),
  );
}

function SkiaHole({ hole, frame, theme }: { hole: GraphHoleMarker; frame: Frame; theme: Theme }) {
  const at = usePlaced(frame, hole.point);
  const cx = useDerivedValue(() => at.value.px);
  const cy = useDerivedValue(() => at.value.py);
  return (
    <Group>
      <Circle cx={cx} cy={cy} r={5} color={theme.elevated} />
      <Circle cx={cx} cy={cy} r={5} color={hole.color} style="stroke" strokeWidth={2.25} />
    </Group>
  );
}

function SkiaMark({
  mark,
  frame,
  theme,
  font,
}: {
  mark: GraphMarkMarker;
  frame: Frame;
  theme: Theme;
  font: SkFont | null;
}) {
  const { width, height, pad } = frame;
  const at = usePlaced(frame, mark.point);
  const textWidth = font ? font.measureText(mark.label).width : markLabelWidth(mark.label);
  const spot = useDerivedValue(
    () => markLabelW(at.value.px, at.value.py, textWidth, GRAPH_TICK_FONT_SIZE, width, height, pad),
  );
  const cx = useDerivedValue(() => at.value.px);
  const cy = useDerivedValue(() => at.value.py);
  const x = useDerivedValue(() => spot.value.x);
  const y = useDerivedValue(() => spot.value.y);
  return (
    <Group>
      <Circle cx={cx} cy={cy} r={MARK_RADIUS + 1.5} color={theme.surface} />
      <Circle cx={cx} cy={cy} r={MARK_RADIUS} color={mark.color} />
      {font ? <HaloText x={x} y={y} text={mark.label} font={font} color={theme.text} halo={theme.surface} /> : null}
    </Group>
  );
}

export function SkiaGraphPoints({
  points,
  frame,
  theme,
  font,
}: {
  points: GraphPoints;
  frame: Frame;
  theme: Theme;
  font: SkFont | null;
}) {
  return (
    <>
      {points.holes.map((hole, i) => (
        <SkiaHole key={`hole-${i}`} hole={hole} frame={frame} theme={theme} />
      ))}
      {points.marks.map((mark, i) => (
        <SkiaMark key={`mark-${i}`} mark={mark} frame={frame} theme={theme} font={font} />
      ))}
    </>
  );
}

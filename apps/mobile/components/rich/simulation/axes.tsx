/**
 * A vector diagram's x and y axes: thin lines under everything else, each with an open
 * arrowhead and its name at its high end. Drawn from the start, before any stage, so the
 * vector is seen leaving their origin and each component lying along one.
 */
import { useMemo } from "react";
import { Path, type SkFont } from "@shopify/react-native-skia";

import type { AxesLayout, AxisLayout } from "@/lib/physics/simulation/axes";
import type { Theme } from "@/lib/theme";
import { HaloText } from "@/components/rich/skia/HaloText";
import { arrowPath } from "@/components/rich/skia/paths";

/** An axis's arrowhead, in px: smaller than a vector's, as the axis is only a guide. */
const AXIS_HEAD = 6;

function Axis({
  axis,
  font,
  fallbacks,
  theme,
}: {
  axis: AxisLayout;
  font: SkFont | null;
  fallbacks: (SkFont | null)[];
  theme: Theme;
}) {
  const { line, label } = axis;
  const path = useMemo(() => {
    const length = Math.hypot(line.x2 - line.x1, line.y2 - line.y1);
    const ux = length > 0 ? (line.x2 - line.x1) / length : 0;
    const uy = length > 0 ? (line.y2 - line.y1) / length : 0;
    return arrowPath(line.x1, line.y1, ux, uy, length, AXIS_HEAD, "open");
  }, [line]);
  return (
    <>
      <Path path={path} color={theme.textTertiary} style="stroke" strokeWidth={1} />
      <HaloText
        x={label.x}
        y={label.y}
        text={label.text}
        font={font}
        fallbacks={fallbacks}
        color={theme.textTertiary}
        halo={theme.bg}
      />
    </>
  );
}

export function SceneAxes({
  axes,
  font,
  fallbacks,
  theme,
}: {
  axes: AxesLayout | undefined;
  font: SkFont | null;
  fallbacks: (SkFont | null)[];
  theme: Theme;
}) {
  if (!axes) return null;
  return (
    <>
      <Axis axis={axes.x} font={font} fallbacks={fallbacks} theme={theme} />
      <Axis axis={axes.y} font={font} fallbacks={fallbacks} theme={theme} />
    </>
  );
}

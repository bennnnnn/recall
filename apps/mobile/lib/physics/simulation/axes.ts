/**
 * A vector diagram's x and y axes on screen: two thin lines through the origin the
 * server set, each from its low end to its high end, with its name just past the
 * arrowhead. The extents and names are the server's (`SimulationAxes`); this only maps
 * them to the canvas and keeps each name on it.
 */
import { placedLabel, type LabelBox, type PlacedLabel, type Segment } from "@/lib/physics/simulation/labels";
import { type SimulationAxes } from "@/lib/physics/simulation/spec";
import { worldToScreen, type SimulationTransform } from "@/lib/physics/simulation/viewport";

/** Gap between an axis's arrowhead and its name, in px. */
const NAME_GAP = 4;

export type AxisLayout = { line: Segment; label: PlacedLabel };
export type AxesLayout = { x: AxisLayout; y: AxisLayout };

/** The axes as drawn, or null for a scene without them. */
export function layoutAxes(
  axes: SimulationAxes | undefined,
  transform: SimulationTransform,
  width: number,
  height: number,
  measureText: (text: string) => number,
  fontSize: number,
): AxesLayout | null {
  if (!axes) return null;
  const { origin } = axes;
  const xLow = worldToScreen(axes.x[0], origin.y, transform);
  const xHigh = worldToScreen(axes.x[1], origin.y, transform);
  const yLow = worldToScreen(origin.x, axes.y[0], transform);
  const yHigh = worldToScreen(origin.x, axes.y[1], transform);
  const keep = (box: LabelBox): LabelBox => ({
    ...box,
    x: Math.min(Math.max(box.x, 0), width - box.width),
    y: Math.min(Math.max(box.y, 0), height - box.height),
  });
  const xWidth = measureText(axes.xLabel);
  const yWidth = measureText(axes.yLabel);
  // "x" past the right-hand arrowhead, on the line; "y" past the top one, beside it.
  const xBox = keep({
    x: xHigh.px + NAME_GAP,
    y: xHigh.py - fontSize / 2,
    width: xWidth,
    height: fontSize,
  });
  const yBox = keep({
    x: yHigh.px - yWidth / 2,
    y: yHigh.py - NAME_GAP - fontSize,
    width: yWidth,
    height: fontSize,
  });
  return {
    x: {
      line: { x1: xLow.px, y1: xLow.py, x2: xHigh.px, y2: xHigh.py },
      label: placedLabel(axes.xLabel, xBox),
    },
    y: {
      line: { x1: yLow.px, y1: yLow.py, x2: yHigh.px, y2: yHigh.py },
      label: placedLabel(axes.yLabel, yBox),
    },
  };
}

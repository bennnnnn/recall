/**
 * How tall a `graph` fence's card will be, so its cell does not jump when the renderer
 * arrives: a number line is a short strip and a trajectory a fixed chart with its play
 * button, where one guess sized for a function plot left a number line's answer under a
 * tall empty gap. Read from the fence's kind with one JSON parse, not the graph parser, so
 * it stays with the chat screen while the renderers load on first use.
 */
import { FIGURE_TITLE_HEIGHT } from "@/components/rich/figure";
import { isJsonRecord, readJson } from "@/lib/fence/json";
import { Space } from "@/lib/space";

/** The fixed charts' canvases: a trajectory's plot and a number line's strip. */
export const TRAJECTORY_CHART_HEIGHT = 220;
export const NUMBER_LINE_HEIGHT = 80;
/** A function plot grows with its list of curves; this is one curve's card. */
const PLOT_CARD_HEIGHT = 280;
/** A figure's margins above and below, and its title line. */
const FIGURE_FRAME = Space.xs * 2 + FIGURE_TITLE_HEIGHT;
const PLAY_BUTTON = Space.xxs + Space.minTouch;

export function graphPlaceholderHeight(content: string): number {
  const spec = readJson(content.trim())?.value;
  if (!isJsonRecord(spec)) return PLOT_CARD_HEIGHT;
  if (spec.type === "number_line") return FIGURE_FRAME + NUMBER_LINE_HEIGHT;
  if (spec.type !== "trajectory") return PLOT_CARD_HEIGHT;
  // A trajectory's dot walks its path: the play button shows when there is a path to walk.
  const moves = Array.isArray(spec.points) && spec.points.length > 1;
  return FIGURE_FRAME + TRAJECTORY_CHART_HEIGHT + (moves ? PLAY_BUTTON : 0);
}

/**
 * What a screen reader hears for a trajectory chart's title and axes.
 *
 * A motion graph's title and axes are the textbook's symbols ("|v|–t", "|v| (m/s)"), which
 * read the same in every language on screen but are read out mark by mark ("vertical bar v
 * vertical bar"). The server names the graph's quantity (`quantity` on the graph fence), and
 * the phone says it in the user's language instead, with the unit the label states.
 */
import type { Translate } from "@/lib/i18n/translate";

export type MotionQuantity = "displacement" | "distance" | "velocity" | "speed" | "acceleration";

const MOTION_QUANTITIES: readonly MotionQuantity[] = [
  "displacement",
  "distance",
  "velocity",
  "speed",
  "acceleration",
];

function isMotionQuantity(raw: unknown): raw is MotionQuantity {
  return MOTION_QUANTITIES.some((quantity) => quantity === raw);
}

/** The fence's quantity when this build knows it; anything else reads as none. */
export function parseMotionQuantity(raw: unknown): MotionQuantity | undefined {
  return isMotionQuantity(raw) ? raw : undefined;
}

/** The unit an axis label states: "m/s" of "|v| (m/s)"; "" for one with none ("x/A"). */
function unitOf(label: string | undefined): string {
  const found = /\(([^()]*)\)\s*$/.exec(label ?? "");
  return found ? found[1] : "";
}

function spoken(name: string, label: string | undefined): string {
  const unit = unitOf(label);
  return unit ? `${name} (${unit})` : name;
}

type Labelled = { x_label?: string; y_label?: string; quantity?: MotionQuantity };

/** The words for `rich.trajectory_a11y`: a motion graph by its quantity's translated name,
 * any other chart by the title and axis labels it shows. */
export function trajectorySpeech(
  spec: Labelled,
  title: string,
  t: Translate,
): { title: string; x: string; y: string } {
  if (!spec.quantity) return { title, x: spec.x_label ?? "x", y: spec.y_label ?? "y" };
  const name = t(`rich.motion_quantity_${spec.quantity}`);
  return {
    title: name,
    x: spoken(t("rich.motion_quantity_time"), spec.x_label),
    y: spoken(name, spec.y_label),
  };
}

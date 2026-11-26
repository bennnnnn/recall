import { parseGraphSpec } from "@/lib/math/graphSpec";
import { trajectorySpeech } from "@/lib/math/trajectorySpeech";
import en from "@/lib/i18n/en.json";
import es from "@/lib/i18n/es.json";

type Bundle = Record<string, string>;
const translate = (bundle: Bundle) => (key: string) => bundle[key] ?? key;

function speedGraph(extra: Record<string, unknown> = {}): string {
  return JSON.stringify({
    type: "trajectory",
    expr: "v(t) = |0 - 9.81*t|",
    variable: "t",
    title: "|v|–t",
    x_label: "t (s)",
    y_label: "|v| (m/s)",
    points: [
      [0, 0],
      [1, 9.81],
    ],
    trajectory_type: "velocity_vs_time",
    quantity: "speed",
    ...extra,
  });
}

describe("trajectorySpeech", () => {
  it("names a motion graph's quantity in words, never its symbols", () => {
    const spec = parseGraphSpec(speedGraph());
    expect(spec).not.toBeNull();
    const words = trajectorySpeech(spec!, "|v|–t", translate(en as Bundle));
    expect(words).toEqual({ title: "Speed", x: "Time (s)", y: "Speed (m/s)" });
    expect(Object.values(words).join(" ")).not.toContain("|");
  });

  it("says them in the user's language", () => {
    const spec = parseGraphSpec(speedGraph());
    expect(trajectorySpeech(spec!, "|v|–t", translate(es as Bundle))).toEqual({
      title: "Rapidez",
      x: "Tiempo (s)",
      y: "Rapidez (m/s)",
    });
  });

  it("says a unitless axis by its name alone", () => {
    const spec = parseGraphSpec(
      speedGraph({ quantity: "displacement", y_label: "x/A", title: "x–t" }),
    );
    expect(trajectorySpeech(spec!, "x–t", translate(en as Bundle)).y).toBe("Displacement");
  });

  it("keeps the labels of a graph with no quantity, or one this build does not know", () => {
    for (const quantity of [undefined, "jerk"]) {
      const spec = parseGraphSpec(speedGraph({ quantity }));
      expect(trajectorySpeech(spec!, "|v|–t", translate(en as Bundle))).toEqual({
        title: "|v|–t",
        x: "t (s)",
        y: "|v| (m/s)",
      });
    }
  });
});

/**
 * Pins what `layoutSimulationScene` returns for one small scene of each kind,
 * so a change to the layout shows up as a reviewed snapshot diff.
 *
 * Numbers are rounded to 0.01 px, a polyline longer than eight points (an arc,
 * a rope) is kept as its length and ends, and the scene's own parts the layout
 * hands back unchanged (`vector`, `angle`, `solid`) are left out.
 */
import {
  layoutSimulationScene,
  parseSimulationSpec,
  simulationTransform,
  simulationViewportHeight,
  type SimulationKind,
} from "@/lib/physics/simulation";

const WIDTH = 312;
const FONT = 11;
const measure = (text: string) => text.length * 6.6;

const SCENES: Record<SimulationKind, object> = {
  projectile_motion: {
    type: "projectile_motion",
    bodies: [
      {
        radius: 0.5,
        role: "primary",
        label: "ball",
        path: [
          [0, 5.5],
          [5, 9.1],
          [10, 10.9],
          [15, 10.9],
          [20, 9.1],
          [25, 5.5],
          [30, 0.5],
        ],
      },
    ],
    x_min: -3,
    x_max: 33,
    y_min: -1,
    y_max: 13,
    arrows: ["velocity", "gravity"],
    arrow_labels: { velocity: "v", gravity: "mg" },
    ground: true,
    solids: [{ rect: [-3, 0, 1, 5], kind: "solid", label: "table" }],
    vectors: [{ anchor: [-2, 0], dx: 0, dy: 5, label: "h = 5 m", role: "measure" }],
    strobe: 4,
  },
  orbit: {
    type: "orbit",
    bodies: [
      {
        radius: 0.4,
        role: "primary",
        path: Array.from({ length: 9 }, (_, i) => [
          6 * Math.cos((Math.PI * i) / 4),
          6 * Math.sin((Math.PI * i) / 4),
        ]),
      },
    ],
    x_min: -8,
    x_max: 8,
    y_min: -8,
    y_max: 8,
    arrows: ["velocity", "centripetal"],
    arrow_labels: { centripetal: "F" },
    centre: [0, 0],
    central_body: { radius: 2, label: "Earth" },
    ground: false,
  },
  collision: {
    type: "collision",
    bodies: [
      {
        radius: 0.4,
        role: "primary",
        label: "2 kg",
        path: [
          [1, 0.4],
          [3, 0.4],
          [5, 0.4],
          [5.5, 0.4],
          [6, 0.4],
        ],
      },
      {
        radius: 0.3,
        role: "secondary",
        label: "1 kg",
        path: [
          [5.7, 0.3],
          [5.7, 0.3],
          [5.7, 0.3],
          [7.5, 0.3],
          [9.3, 0.3],
        ],
      },
    ],
    x_min: 0,
    x_max: 10,
    y_min: -0.5,
    y_max: 2,
    arrows: ["velocity"],
    ground: true,
  },
  incline: {
    type: "incline",
    bodies: [
      {
        radius: 0.5,
        role: "primary",
        shape: "box",
        label: "2 kg",
        path: [
          [2, 3],
          [2.87, 2.5],
          [3.73, 2],
          [4.6, 1.5],
          [5.46, 1],
        ],
      },
    ],
    x_min: 0,
    x_max: 9,
    y_min: -0.5,
    y_max: 5,
    arrows: ["gravity", "normal", "friction"],
    arrow_labels: { normal: "N", friction: "f" },
    incline_deg: 30,
    ground: true,
    angles: [{ vertex: [6.2, 0], start_deg: 150, end_deg: 180, label: "30°" }],
  },
  lever: {
    type: "lever",
    bodies: [],
    beam: [-4, 0, 4, 0],
    pivot: [0, 0],
    vectors: [
      { anchor: [-3, 0], dx: 0, dy: -2, label: "20 N", role: "force" },
      { anchor: [2, 0], dx: 0, dy: -3, label: "30 N", role: "result" },
    ],
    angles: [{ vertex: [0, 0], start_deg: 150, end_deg: 30, arrow: true, label: "M" }],
    x_min: -5,
    x_max: 5,
    y_min: -3,
    y_max: 3,
    arrows: [],
  },
  free_body: {
    type: "free_body",
    bodies: [
      {
        radius: 0.3,
        role: "primary",
        shape: "box",
        label: "5 kg",
        path: [
          [-0.5, 2],
          [-0.5, 1.8],
          [-0.5, 1.4],
          [-0.5, 0.8],
        ],
      },
      {
        radius: 0.25,
        role: "secondary",
        shape: "box",
        label: "3 kg",
        path: [
          [0.5, 1.5],
          [0.5, 1.7],
          [0.5, 2.1],
          [0.5, 2.7],
        ],
      },
    ],
    pulley: { centre: [0, 4], radius: 0.5 },
    tethers: [
      { anchor: [-0.5, 4], body: 0 },
      { anchor: [0.5, 4], body: 1 },
    ],
    vectors: [
      { anchor: [0, 0.3], dx: 0, dy: 1, label: "T", role: "force", body: 0 },
      { anchor: [0, 0.25], dx: 0, dy: 1, label: "T", role: "force", body: 1 },
      { anchor: [-0.6, 0], dx: 0, dy: -1, label: "a", role: "motion", body: 0 },
    ],
    x_min: -2,
    x_max: 2,
    y_min: 0,
    y_max: 5,
    arrows: [],
  },
  vector_sum: {
    type: "vector_sum",
    bodies: [],
    vectors: [
      { anchor: [0, 0], dx: 3, dy: 0, label: "3 N", role: "force" },
      { anchor: [3, 0], dx: 0, dy: 4, label: "4 N", role: "force" },
      { anchor: [0, 0], dx: 3, dy: 4, label: "5 N", role: "result" },
    ],
    angles: [{ vertex: [0, 0], start_deg: 0, end_deg: 53.13, label: "53.1°", role: "result" }],
    x_min: -1,
    x_max: 5,
    y_min: -1,
    y_max: 5,
    arrows: [],
  },
  spring: {
    type: "spring",
    bodies: [
      {
        radius: 0.3,
        role: "primary",
        shape: "box",
        path: [
          [1, 0.3],
          [0.25, 0.3],
          [-0.5, 0.3],
          [0.25, 0.3],
          [1, 0.3],
        ],
      },
    ],
    anchor: [-2, 0.3],
    x_min: -2.5,
    x_max: 2,
    y_min: 0,
    y_max: 1.5,
    arrows: [],
    ground: true,
  },
  pendulum: {
    type: "pendulum",
    bodies: [
      {
        radius: 0.2,
        role: "primary",
        label: "bob",
        path: Array.from({ length: 7 }, (_, i) => {
          const theta = 0.4 * Math.cos((Math.PI * i) / 3);
          return [2 * Math.sin(theta), 3 - 2 * Math.cos(theta)];
        }),
      },
    ],
    tethers: [{ anchor: [0, 3], body: 0 }],
    angles: [{ vertex: [0, 3], start_deg: 270, end_deg: 292.9, label: "θ" }],
    x_min: -1.5,
    x_max: 1.5,
    y_min: 0.5,
    y_max: 3.5,
    arrows: ["velocity", "gravity"],
    arrow_labels: { gravity: "mg" },
    strobe: 3,
  },
};

function isPoint(value: unknown): boolean {
  return typeof value === "object" && value !== null && "px" in value && "py" in value;
}

const PASSED_THROUGH = new Set(["vector", "angle", "solid"]);

function compact(value: unknown): unknown {
  if (typeof value === "number") return Math.round(value * 100) / 100 || 0;
  if (Array.isArray(value)) {
    if (value.length > 8 && value.every(isPoint)) {
      const last = value[value.length - 1];
      return { points: value.length, first: compact(value[0]), last: compact(last) };
    }
    return value.map(compact);
  }
  if (typeof value === "object" && value !== null) {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => !PASSED_THROUGH.has(key))
        .map(([key, entry]) => [key, compact(entry)]),
    );
  }
  return value;
}

describe("layoutSimulationScene", () => {
  it.each(Object.keys(SCENES) as SimulationKind[])("lays out a %s scene as before", (kind) => {
    const spec = parseSimulationSpec(JSON.stringify(SCENES[kind]));
    if (!spec) throw new Error(`${kind} fixture did not parse`);
    const height = simulationViewportHeight(spec, WIDTH, 24, 136, 240);
    const transform = simulationTransform(spec, WIDTH, height, 24);
    const layout = layoutSimulationScene(spec, transform, WIDTH, height, measure, FONT);
    const lines = Object.entries(layout).map(
      ([key, entry]) => `${key}: ${JSON.stringify(compact(entry))}`,
    );
    expect(lines.join("\n")).toMatchSnapshot();
  });
});

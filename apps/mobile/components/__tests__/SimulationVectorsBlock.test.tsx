/**
 * Pictures a physics reply describes and the server lays out
 * (`apps/api/app/modules/physics/scene_drawing/vectors.py`): two cars meeting at a
 * junction, as the server sent them for the owner's question (live, 2026-11-25), the
 * cars moving off together after it, and a walk drawn head to tail.
 */
import { render } from "@testing-library/react-native";

import { SimulationBlock } from "@/components/rich/SimulationBlock";
import { parseSimulationSpec } from "@/lib/physics/simulation";

const HIDDEN = { includeHiddenElements: true };

jest.mock("@/lib/motion", () => ({
  ...jest.requireActual("@/lib/motion"),
  useReduceMotion: () => false,
  useReduceMotionSetting: () => false,
}));

const JUNCTION = JSON.stringify({
  type: "free_body",
  title: "Before the Collision",
  bodies: [
    { label: "Car A, 1000 kg", radius: 0.16, path: [[0, -1], [0, -1]], role: "primary", shape: "box" },
    { label: "Car B, 1300 kg", radius: 0.16, path: [[1, 0], [1, 0]], role: "secondary", shape: "box" },
  ],
  x_min: -0.6,
  x_max: 1.6,
  y_min: -1.6,
  y_max: 0.6,
  arrows: [],
  ground: false,
  vectors: [
    { anchor: [0, 0.2], dx: 0, dy: 20, label: "20 m/s", role: "motion", body: 0 },
    { anchor: [-0.2, 0], dx: -16, dy: 0, label: "16 m/s", role: "motion", body: 1 },
  ],
  alt: "Velocities: Car A, 1000 kg: 20 m/s north; Car B, 1300 kg: 16 m/s west",
  title_key: "before_collision",
  axes: { origin: [0, 0], x: [-0.52, 1.52], y: [-1.52, 0.52], x_label: "E", y_label: "N" },
});

const AFTER = JSON.stringify({
  type: "free_body",
  title: "After the Collision",
  bodies: [{ label: "Car A + Car B", radius: 0.208, path: [[0, 0], [0, 0]], role: "primary" }],
  x_min: -1.2,
  x_max: 1.2,
  y_min: -1.2,
  y_max: 1.2,
  arrows: [],
  ground: false,
  vectors: [
    { anchor: [-0.1615, 0.1553], dx: -9.0435, dy: 8.6957, label: "12.55 m/s", role: "motion", body: 0 },
  ],
  angles: [{ vertex: [0, 0], start_deg: 136.12, end_deg: 180, label: "43.88°", arrow: false, role: "result" }],
  alt: "Car A and Car B move off together at 12.55 m/s",
  title_key: "after_collision",
  axes: { origin: [0, 0], x: [-1.12, 1.12], y: [-1.12, 1.12], x_label: "E", y_label: "N" },
});

const WALK = JSON.stringify({
  type: "vector_sum",
  title: "Displacements",
  bodies: [],
  x_min: -880,
  x_max: 4880,
  y_min: -880,
  y_max: 3880,
  arrows: [],
  ground: false,
  vectors: [
    { anchor: [0, 0], dx: 0, dy: 3000, label: "3 km", role: "force", stage: 0 },
    { anchor: [0, 3000], dx: 4000, dy: 0, label: "4 km", role: "force", stage: 1 },
    { anchor: [0, 0], dx: 4000, dy: 3000, label: "R = 5 km", role: "result", stage: 2 },
  ],
  angles: [
    { vertex: [0, 0], start_deg: 36.87, end_deg: 90, label: "53.13°", arrow: false, role: "result", stage: 2 },
  ],
  alt: "Displacements: 3 km north; 4 km east",
  title_key: "displacements",
  axes: { origin: [0, 0], x: [-879.92, 4879.92], y: [-879.92, 3879.92], x_label: "E", y_label: "N" },
});

describe("SimulationBlock: arrows a reply describes", () => {
  it("reads every picture with its translatable title", () => {
    expect(parseSimulationSpec(JUNCTION)?.titleKey).toBe("before_collision");
    expect(parseSimulationSpec(AFTER)?.titleKey).toBe("after_collision");
    expect(parseSimulationSpec(WALK)?.titleKey).toBe("displacements");
  });

  it("draws two cars at a junction, each with its velocity riding on it", async () => {
    const { getAllByTestId, getByLabelText, getByText, queryByTestId } = await render(
      <SimulationBlock content={JUNCTION} />,
    );

    expect(getAllByTestId("simulation-body", HIDDEN)).toHaveLength(2);
    expect(getAllByTestId("simulation-body-box", HIDDEN)).toHaveLength(2);
    expect(getAllByTestId("simulation-body-label", HIDDEN)).toHaveLength(2);
    expect(getAllByTestId("simulation-vector-motion", HIDDEN)).toHaveLength(2);
    expect(getAllByTestId("simulation-vector-attached", HIDDEN)).toHaveLength(2);
    expect(getByLabelText(/Car A, 1000 kg: 20 m\/s north/)).toBeTruthy();
    expect(getByText("Before the Collision")).toBeTruthy();
    // A still picture: nothing to play.
    expect(queryByTestId("simulation-control")).toBeNull();
  });

  it("draws the cars moving off as one, with the angle off the west axis", async () => {
    const { getAllByTestId, getByTestId } = await render(<SimulationBlock content={AFTER} />);

    expect(getAllByTestId("simulation-body", HIDDEN)).toHaveLength(1);
    expect(getAllByTestId("simulation-vector-motion", HIDDEN)).toHaveLength(1);
    expect(getByTestId("simulation-angle-result", HIDDEN)).toBeTruthy();
  });

  it("builds a walk leg by leg, its resultant last", async () => {
    const { getAllByTestId, getByLabelText } = await render(<SimulationBlock content={WALK} />);

    expect(getAllByTestId("simulation-vector-force", HIDDEN)).toHaveLength(2);
    expect(getAllByTestId("simulation-vector-result", HIDDEN)).toHaveLength(1);
    expect(getByLabelText(/3 km north; 4 km east/)).toBeTruthy();
  });
});

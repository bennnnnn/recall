/**
 * P14: the simulation scene's render behaviour.
 *
 * Its arithmetic is asserted as pure functions in
 * `lib/__tests__/simulationScene.test.ts`. What is left here is the part only a
 * render can prove: that nothing moves until the user asks, that Reduce Motion
 * still gets a real diagram rather than an empty box, and that an arrow is
 * never drawn without the thing it points at.
 */
import { render } from "@testing-library/react-native";

import { SimulationBlock } from "@/components/rich/SimulationBlock";

const mockUseReduceMotion = jest.fn(() => false);
jest.mock("@/lib/motion", () => ({
  ...jest.requireActual("@/lib/motion"),
  useReduceMotion: () => mockUseReduceMotion(),
}));

const PROJECTILE = JSON.stringify({
  type: "projectile_motion",
  title: "Projectile",
  bodies: [
    {
      radius: 0.5,
      role: "primary",
      path: [
        [0, 0],
        [10, 7],
        [20, 10],
        [30, 7],
        [40, 0],
      ],
    },
  ],
  x_min: 0,
  x_max: 42,
  y_min: 0,
  y_max: 14,
  arrows: ["velocity", "gravity"],
  ground: true,
});

const ORBIT = JSON.stringify({
  type: "orbit",
  title: "Circular Motion",
  bodies: [
    {
      radius: 0.4,
      role: "primary",
      path: [
        [5, 0],
        [0, 5],
        [-5, 0],
        [0, -5],
        [5, 0],
      ],
    },
  ],
  x_min: -7,
  x_max: 7,
  y_min: -7,
  y_max: 7,
  arrows: ["velocity", "centripetal"],
  centre: [0, 0],
  ground: false,
});

beforeEach(() => {
  mockUseReduceMotion.mockReturnValue(false);
});

describe("SimulationBlock", () => {
  it("renders a projectile scene with a body, its arrows and the ground", async () => {
    const { getByTestId, getAllByTestId } = await render(<SimulationBlock content={PROJECTILE} />);

    expect(getAllByTestId("simulation-body").length).toBe(1);
    expect(getByTestId("simulation-arrow-velocity")).toBeTruthy();
    expect(getByTestId("simulation-arrow-gravity")).toBeTruthy();
    expect(getByTestId("simulation-ground")).toBeTruthy();
  });

  it("renders an orbit with its centre and a centripetal arrow", async () => {
    // The kind that drew nothing at all before this ticket.
    const { getByTestId, queryByTestId } = await render(<SimulationBlock content={ORBIT} />);

    expect(getByTestId("simulation-centre")).toBeTruthy();
    expect(getByTestId("simulation-arrow-centripetal")).toBeTruthy();
    expect(queryByTestId("simulation-ground")).toBeNull();
  });

  it("offers play rather than starting on its own", async () => {
    // Same rule P3 settled: a chat scrolling past should not set half a dozen
    // animations running.
    const { getByTestId } = await render(<SimulationBlock content={PROJECTILE} />);

    expect(getByTestId("simulation-play")).toBeTruthy();
  });

  it("falls back to a static diagram under Reduce Motion", async () => {
    // Not a blank space: the body and its force arrows at the first sample are
    // a free-body diagram, which is most of what the picture is for.
    mockUseReduceMotion.mockReturnValue(true);
    const { getByTestId, queryByTestId } = await render(<SimulationBlock content={PROJECTILE} />);

    expect(getByTestId("simulation-static")).toBeTruthy();
    expect(getByTestId("simulation-body")).toBeTruthy();
    expect(getByTestId("simulation-arrow-gravity")).toBeTruthy();
    expect(getByTestId("simulation-ground")).toBeTruthy();
    expect(queryByTestId("simulation-play")).toBeNull();
  });

  it("never draws a centripetal arrow without a centre", async () => {
    // "Toward the centre" with nothing at the centre would point at the origin
    // of the scene box instead — a confident arrow at the wrong target.
    const noCentre = JSON.stringify({ ...JSON.parse(ORBIT), centre: undefined });
    const { queryByTestId } = await render(<SimulationBlock content={noCentre} />);

    expect(queryByTestId("simulation-arrow-centripetal")).toBeNull();
    expect(queryByTestId("simulation-centre")).toBeNull();
    // The rest of the scene still renders.
    expect(queryByTestId("simulation-arrow-velocity")).toBeTruthy();
  });

  it("shows its fallback rather than half a scene when the spec is unreadable", async () => {
    const { queryByTestId } = await render(<SimulationBlock content="{ not json" />);

    expect(queryByTestId("simulation-body")).toBeNull();
    expect(queryByTestId("simulation-play")).toBeNull();
  });

  it("renders every body in a multi-body scene", async () => {
    // The shape collisions will use: two bodies, one clock.
    const pair = JSON.parse(PROJECTILE);
    const twoBodies = JSON.stringify({
      ...pair,
      bodies: [
        pair.bodies[0],
        { ...pair.bodies[0], role: "secondary" },
      ],
    });
    const { getAllByTestId } = await render(<SimulationBlock content={twoBodies} />);

    expect(getAllByTestId("simulation-body").length).toBe(2);
  });
});

const COLLISION = JSON.stringify({
  type: "collision",
  title: "Collision",
  bodies: [
    { radius: 0.38, role: "primary", path: [[-2, 0], [-1, 0], [-0.38, 0], [0, 0]] },
    { radius: 0.3, role: "secondary", path: [[0.3, 0], [0.3, 0], [0.3, 0], [1.2, 0]] },
  ],
  x_min: -3,
  x_max: 3,
  y_min: -1,
  y_max: 1,
  arrows: ["velocity"],
});

const INCLINE = JSON.stringify({
  type: "incline",
  title: "Inclined Plane",
  bodies: [{ radius: 0.36, role: "primary", path: [[0, 3], [0, 3]] }],
  x_min: -1,
  x_max: 6.2,
  y_min: -1,
  y_max: 4,
  arrows: ["gravity", "normal", "friction"],
  incline_deg: 30,
});

describe("SimulationBlock: collisions and inclines", () => {
  it("renders both bodies of a collision", async () => {
    // The scene a number cannot replace: "1.00 m/s and 4.00 m/s" says nothing
    // about which ball ends up ahead or whether either turns around.
    const { getAllByTestId, queryByTestId } = await render(<SimulationBlock content={COLLISION} />);

    expect(getAllByTestId("simulation-body").length).toBe(2);
    expect(getAllByTestId("simulation-arrow-velocity").length).toBe(2);
    expect(queryByTestId("simulation-ground")).toBeNull();
    expect(queryByTestId("simulation-slope")).toBeNull();
  });

  it("draws the slope an incline block sits on", async () => {
    const { getByTestId, queryByTestId } = await render(<SimulationBlock content={INCLINE} />);

    expect(getByTestId("simulation-slope")).toBeTruthy();
    expect(getByTestId("simulation-arrow-normal")).toBeTruthy();
    expect(getByTestId("simulation-arrow-friction")).toBeTruthy();
    expect(getByTestId("simulation-arrow-gravity")).toBeTruthy();
    // Not a projectile: no flat ground line under a slope.
    expect(queryByTestId("simulation-ground")).toBeNull();
  });

  it("gives a held block its free-body diagram under Reduce Motion", async () => {
    // For two of the three friction ops the block never moves, so the still
    // picture is not a fallback — it is the answer's illustration.
    mockUseReduceMotion.mockReturnValue(true);
    const { getByTestId, queryByTestId } = await render(<SimulationBlock content={INCLINE} />);

    expect(getByTestId("simulation-static")).toBeTruthy();
    expect(getByTestId("simulation-arrow-normal")).toBeTruthy();
    expect(getByTestId("simulation-arrow-friction")).toBeTruthy();
    expect(getByTestId("simulation-slope")).toBeTruthy();
    expect(queryByTestId("simulation-play")).toBeNull();
  });

  it("never draws a normal or friction arrow without a slope", async () => {
    const noSlope = JSON.stringify({ ...JSON.parse(INCLINE), incline_deg: undefined });
    const { queryByTestId } = await render(<SimulationBlock content={noSlope} />);

    expect(queryByTestId("simulation-arrow-normal")).toBeNull();
    expect(queryByTestId("simulation-arrow-friction")).toBeNull();
    expect(queryByTestId("simulation-slope")).toBeNull();
    // Weight still points down whatever the surface does.
    expect(queryByTestId("simulation-arrow-gravity")).toBeTruthy();
  });
});

const LEVER = JSON.stringify({
  type: "lever",
  title: "Moments",
  bodies: [],
  beam: [-2.5, 0, 2.5, 0],
  pivot: [0, 0],
  vectors: [
    { anchor: [-2, 0], dx: 0, dy: -1, label: "5 N at 2 m", role: "force" },
    { anchor: [1, 0], dx: 0, dy: -1, label: "10 N at 1.00 m", role: "result" },
  ],
  x_min: -2.9,
  x_max: 2.9,
  y_min: -1.4,
  y_max: 1.4,
  arrows: [],
});

const FREE_BODY = JSON.stringify({
  type: "free_body",
  title: "Free-Body Diagram",
  bodies: [{ radius: 0.32, role: "primary", label: "5 kg", path: [[0, 0], [0, 0]] }],
  vectors: [
    { anchor: [0, 0], dx: 0, dy: 1, label: "T = 59.05 N", role: "result" },
    { anchor: [0, 0], dx: 0, dy: -1, label: "W = 49.05 N", role: "force" },
  ],
  x_min: -2,
  x_max: 2,
  y_min: -2,
  y_max: 2,
  arrows: [],
});

describe("SimulationBlock: still figures", () => {
  it("draws a see-saw as beam, pivot and two labelled loads", async () => {
    const { getByTestId, getAllByTestId } = await render(<SimulationBlock content={LEVER} />);

    expect(getByTestId("simulation-beam")).toBeTruthy();
    expect(getByTestId("simulation-pivot")).toBeTruthy();
    expect(getAllByTestId("simulation-vector-label").length).toBe(2);
    // The arm that was the question is the one drawn in the answer's colour.
    expect(getAllByTestId("simulation-vector-result").length).toBe(1);
    expect(getAllByTestId("simulation-vector-force").length).toBe(1);
  });

  it("offers no Play on a scene with nothing to play", async () => {
    // A button that does nothing when pressed is worse than no button.
    const { queryByTestId } = await render(<SimulationBlock content={LEVER} />);

    expect(queryByTestId("simulation-play")).toBeNull();
  });

  it("shows each stated force with the magnitude the solver computed", async () => {
    // The labels carry the numbers, so the picture cannot disagree with the
    // answer pill above it.
    //
    // Read off the accessibility label rather than with getByText: an SVG
    // <Text> renders as a native RNSVGText whose content is not a text node a
    // test — or a screen reader — can reach, which is why the component puts
    // the label on the group too.
    const { getByLabelText } = await render(<SimulationBlock content={FREE_BODY} />);

    expect(getByLabelText("T = 59.05 N")).toBeTruthy();
    expect(getByLabelText("W = 49.05 N")).toBeTruthy();
  });

  it("draws the block a free-body diagram is about", async () => {
    const { getByTestId, queryByTestId } = await render(<SimulationBlock content={FREE_BODY} />);

    expect(getByTestId("simulation-body")).toBeTruthy();
    // Still figure: no beam, and nothing to play.
    expect(queryByTestId("simulation-beam")).toBeNull();
    expect(queryByTestId("simulation-play")).toBeNull();
  });

  it("keeps its figure under Reduce Motion", async () => {
    // Nothing was moving, so there is nothing to take away.
    mockUseReduceMotion.mockReturnValue(true);
    const { getByTestId, getAllByTestId } = await render(<SimulationBlock content={LEVER} />);

    expect(getByTestId("simulation-beam")).toBeTruthy();
    expect(getAllByTestId("simulation-vector-label").length).toBe(2);
  });
});

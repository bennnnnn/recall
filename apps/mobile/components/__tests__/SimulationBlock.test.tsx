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

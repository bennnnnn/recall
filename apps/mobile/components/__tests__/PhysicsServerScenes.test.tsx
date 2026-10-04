/** Actual physics solver payloads must all render with native Skia components. */
import { render } from "@testing-library/react-native";

import { SimulationBlock } from "@/components/rich/SimulationBlock";
import fixtures from "@/lib/__tests__/fixtures/physicsNativeScenes.json";
import { parseSimulationSpec, simulationHasMotion } from "@/lib/physics/simulation";

const mockUseReduceMotion = jest.fn(() => false);
jest.mock("@/lib/motion", () => ({
  ...jest.requireActual("@/lib/motion"),
  useReduceMotion: () => mockUseReduceMotion(),
}));

beforeEach(() => mockUseReduceMotion.mockReturnValue(false));

it.each(fixtures)("renders the server's $name scene and its correct playback state", async (fixture) => {
  const content = JSON.stringify(fixture.scene);
  const spec = parseSimulationSpec(content);
  expect(spec).not.toBeNull();
  expect(simulationHasMotion(spec)).toBe(fixture.animated);
  const view = await render(<SimulationBlock content={content} />);
  expect(view.queryByText("rich.simulation_error")).toBeNull();
  expect(view.getByTestId("simulation-canvas")).toBeTruthy();
  expect(view.queryAllByTestId("simulation-body")).toHaveLength(fixture.scene.bodies.length);
  expect(Boolean(view.queryByTestId("simulation-control"))).toBe(fixture.animated);
});

it.each(fixtures)("keeps the server's $name scene visible with reduced motion", async (fixture) => {
  mockUseReduceMotion.mockReturnValue(true);
  const view = await render(<SimulationBlock content={JSON.stringify(fixture.scene)} />);
  expect(view.queryByText("rich.simulation_error")).toBeNull();
  expect(view.getByTestId("simulation-canvas")).toBeTruthy();
  expect(view.queryByTestId("simulation-control")).toBeNull();
  expect(view.queryAllByTestId("simulation-body")).toHaveLength(fixture.scene.bodies.length);
});

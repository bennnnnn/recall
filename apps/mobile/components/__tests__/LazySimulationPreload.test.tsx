import { StyleSheet } from "react-native";
import { act, render, screen } from "@testing-library/react-native";

import { LazySimulationBlock, preloadFigures } from "@/components/rich/LazyHeavyRich";

const mockLoads: string[] = [];
jest.mock("@/components/rich/simulationPlaceholder", () => {
  mockLoads.push("sizing");
  return { simulationFencePlaceholderHeight: jest.fn(() => 321) };
});
// The scene's renderer never draws here, so its placeholder stays on screen.
jest.mock("@/components/rich/SimulationBlock", () => {
  mockLoads.push("scene");
  return {
    SimulationBlock: () => {
      throw new Promise(() => {});
    },
  };
});
jest.mock("@/components/rich/diagrams/PhysicsDiagram", () => {
  mockLoads.push("diagram");
  return { PhysicsDiagram: () => null };
});
jest.mock("@/components/rich/FunctionGraphBlock", () => {
  mockLoads.push("graph");
  return { FunctionGraphBlock: () => null };
});

// A graph or scene under a settled reply waited seconds for its renderer behind a spinner.
describe("preloadFigures", () => {
  it("loads the figures' renderers and the scene sizing ahead of the first answer, once", async () => {
    expect(mockLoads).toEqual([]);
    await act(async () => {
      preloadFigures();
      preloadFigures();
    });
    expect([...mockLoads].sort()).toEqual(["diagram", "graph", "scene", "sizing"]);

    await render(<LazySimulationBlock content={'{"type":"projectile_motion"}'} />);
    const placeholder = screen.getByTestId("rich-load-placeholder");
    expect(StyleSheet.flatten(placeholder.props.style).height).toBe(321);
    expect(mockLoads).toHaveLength(4);
  });
});

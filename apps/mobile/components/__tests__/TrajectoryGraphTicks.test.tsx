import { render } from "@testing-library/react-native";
import { Dimensions } from "react-native";

import { FunctionGraphBlock } from "@/components/rich/FunctionGraphBlock";

const mockSvgText = jest.fn((_props: Record<string, unknown>) => null);
jest.mock("react-native-svg", () => ({
  ...jest.requireActual("react-native-svg"),
  __esModule: true,
  Text: (props: Record<string, unknown>) => mockSvgText(props),
}));

describe("physics trajectory time labels", () => {
  beforeEach(() => {
    jest.spyOn(Dimensions, "get").mockReturnValue({ width: 390, height: 844, scale: 3, fontScale: 1 });
    mockSvgText.mockClear();
  });
  afterEach(() => jest.restoreAllMocks());

  it.each([
    { end: 2.1, points: [[0, 20], [1, 15], [2, 0], [2.1, 0]], labels: ["0.5", "1", "1.5", "2"] },
    { end: 1.05, points: [[0, 20], [0.5, 18.75], [1, 15], [1.05, 14.4875]], labels: ["0.2", "0.4", "0.6", "0.8", "1"] },
  ])("places accurate time labels on the 0–$end second viewport", async ({ end, points, labels }) => {
    await render(<FunctionGraphBlock content={JSON.stringify({
      type: "trajectory", expr: "h(t)=20-5*t^2", points,
      x_min: 0, x_max: end, x_label: "Time (s)", y_label: "Height (m)",
      trajectory_type: "position_vs_time",
    })} />);
    // The time axis sits at y=192 with labels16px below it; y-axis
    // labels are end-anchored and must not be confused with time ticks.
    const timeLabels = mockSvgText.mock.calls.map(([props]) => props)
      .filter((props) => props.y === 208 && props.textAnchor === "middle");
    expect(timeLabels.map((props) => props.children)).toEqual(labels);
    for (const tick of timeLabels) {
      // Screen width390 gives342px SVG, with28px at either edge.
      // Check the rendered coordinate represents the displayed time.
      const timeAtCoordinate = (Number(tick.x) - 28) * end / (342 - 56);
      expect(timeAtCoordinate).toBeCloseTo(Number(tick.children), 10);
    }
  });
});

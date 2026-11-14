import { render } from "@testing-library/react-native";
import { StyleSheet } from "react-native";

import { FunctionGraphBlock } from "@/components/rich/FunctionGraphBlock";
import { darkTheme, lightTheme } from "@/lib/theme";

let mockScheme: "light" | "dark" = "light";
const mockPolyline = jest.fn((_props: Record<string, unknown>) => null);

jest.mock("@/lib/colorScheme", () => ({
  useResolvedColorScheme: () => mockScheme,
}));
jest.mock("@/lib/skiaAvailability", () => ({ isSkiaAvailable: () => false }));
jest.mock("react-native-svg", () => ({
  ...jest.requireActual("react-native-svg"),
  __esModule: true,
  Polyline: (props: Record<string, unknown>) => mockPolyline(props),
}));

describe("comparison graph series", () => {
  it.each([lightTheme, darkTheme])("distinguishes curves and matching series dots in $scheme mode", async (theme) => {
    mockScheme = theme.scheme;
    mockPolyline.mockClear();
    const content = JSON.stringify({
      type: "function", expr: "x**2", expr2: "2*x", title: "Comparison",
      points: [[-2, 4], [0, 0], [2, 4]], points2: [[-2, -4], [0, 0], [2, 4]],
      label: "Parabola", label2: "Line",
    });
    const { getByLabelText } = await render(<FunctionGraphBlock content={content} />);
    const strokes = mockPolyline.mock.calls.map(([props]) => props.stroke);
    expect(strokes).toEqual([theme.graphSeries[0], theme.graphSeries[1]]);
    expect(strokes[0]).not.toBe(strokes[1]);
    // Each curve's legend is its maths, a button that opens its field.
    expect(getByLabelText("rich.graph_expr_a11y, y = x^2")).toBeOnTheScreen();
    expect(getByLabelText("rich.graph_expr_a11y, y = 2*x")).toBeOnTheScreen();
    for (const color of [theme.graphSeries[0], theme.graphSeries[1]]) {
      const marker = mockPolyline.mock.calls
        .map(([props]) => props)
        .find((props) => props.stroke === color);
      expect(marker).toBeTruthy();
    }
    // The legend's row: the nearest ancestor holding a colour swatch.
    let tree = getByLabelText("rich.graph_expr_a11y, y = x^2").parent;
    const swatchIn = (node: typeof tree) =>
      node?.children.find(
        (child) => typeof child !== "string" && StyleSheet.flatten(child.props.style)?.backgroundColor,
      );
    while (tree && !swatchIn(tree)) tree = tree.parent;
    expect(tree).toBeTruthy();
    const swatch = swatchIn(tree);
    expect(
      swatch && typeof swatch !== "string" && StyleSheet.flatten(swatch.props.style).backgroundColor,
    ).toBe(theme.graphSeries[0]);
  });
});

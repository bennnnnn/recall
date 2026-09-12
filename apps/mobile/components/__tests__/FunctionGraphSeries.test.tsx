import { render } from "@testing-library/react-native";
import { StyleSheet } from "react-native";

import { FunctionGraphBlock } from "@/components/rich/FunctionGraphBlock";
import { darkTheme, lightTheme } from "@/lib/theme";

let mockScheme: "light" | "dark" = "light";
const mockPolyline = jest.fn((_props: Record<string, unknown>) => null);

jest.mock("@/hooks/useResolvedColorScheme", () => ({
  useResolvedColorScheme: () => mockScheme,
}));
jest.mock("react-native-svg", () => ({
  ...jest.requireActual("react-native-svg"),
  __esModule: true,
  Polyline: (props: Record<string, unknown>) => mockPolyline(props),
}));

describe("comparison graph series", () => {
  it.each([lightTheme, darkTheme])("distinguishes curves and matching legend dots in $scheme mode", async (theme) => {
    mockScheme = theme.scheme;
    mockPolyline.mockClear();
    const content = JSON.stringify({
      type: "function", expr: "x**2", expr2: "2*x", title: "Comparison",
      points: [[-2, 4], [0, 0], [2, 4]], points2: [[-2, -4], [0, 0], [2, 4]],
      label: "Parabola", label2: "Line",
    });
    const { getByText } = await render(<FunctionGraphBlock content={content} />);
    const strokes = mockPolyline.mock.calls.map(([props]) => props.stroke);
    expect(strokes).toEqual([theme.primary, theme.text]);
    expect(strokes[0]).not.toBe(strokes[1]);
    for (const [label, color] of [["Parabola", strokes[0]], ["Line", strokes[1]]] as const) {
      const item = getByText(label).parent!;
      const marker = item.children.find((child) => typeof child !== "string" && StyleSheet.flatten(child.props.style)?.backgroundColor);
      expect(marker && typeof marker !== "string" && StyleSheet.flatten(marker.props.style).backgroundColor).toBe(color);
    }
  });
});

import { render } from "@testing-library/react-native";

import { FunctionGraphBlock } from "@/components/rich/FunctionGraphBlock";

const mockPolyline = jest.fn((_props: Record<string, unknown>) => null);
jest.mock("react-native-svg", () => ({
  ...jest.requireActual("react-native-svg"),
  __esModule: true,
  Polyline: (props: Record<string, unknown>) => mockPolyline(props),
}));

describe("sampled conic graph rendering", () => {
  it.each([
    ["x**2 + y**2 = 1", 1, 1],
    ["x**2/9 + y**2/4 = 1", 3, 2],
  ] as const)("preserves the actual axis ratio for %s", async (expr, radiusX, radiusY) => {
    mockPolyline.mockClear();
    const points = Array.from({ length: 97 }, (_, i) => {
      const angle = i * Math.PI / 48;
      return [radiusX * Math.cos(angle), radiusY * Math.sin(angle)];
    });
    const content = JSON.stringify({
      type: "function", expr, title: expr, points,
      x_min: -2 * radiusX, x_max: 2 * radiusX,
      y_min: -2 * radiusY, y_max: 2 * radiusY,
    });
    const { toJSON } = await render(<FunctionGraphBlock content={content} />);
    const drawn = String(mockPolyline.mock.calls[0][0].points).split(" ").map((point) => point.split(",").map(Number));
    expect(drawn).toHaveLength(97);
    const width = Math.max(...drawn.map(([x]) => x)) - Math.min(...drawn.map(([x]) => x));
    const height = Math.max(...drawn.map(([, y]) => y)) - Math.min(...drawn.map(([, y]) => y));
    expect(width / height).toBeCloseTo(radiusX / radiusY, 3);
    if (radiusX === 1) {
      const tree = JSON.stringify(toJSON());
      expect(tree).toContain('"content":"-0.5"');
      expect(tree).toContain('"content":"0.5"');
    }
  });
});

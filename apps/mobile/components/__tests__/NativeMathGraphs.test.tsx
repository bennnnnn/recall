import { render } from "@testing-library/react-native";

import { FunctionGraphBlock } from "@/components/rich/FunctionGraphBlock";

jest.mock("@expo/vector-icons", () => ({ Ionicons: "Ionicons" }));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("@/lib/skiaAvailability", () => ({ isSkiaAvailable: () => true }));

describe("native math graphs", () => {
  it("uses Skia for the inline function card", async () => {
    const content = JSON.stringify({
      type: "function",
      expr: "x**2",
      points: [
        [-2, 4],
        [0, 0],
        [2, 4],
      ],
    });
    const { getByTestId } = await render(<FunctionGraphBlock content={content} />);

    expect(getByTestId("skia-graph-card")).toBeOnTheScreen();
  });

  it("uses Skia for a number-line solution", async () => {
    const content = JSON.stringify({
      type: "number_line",
      expr: "x > 3",
      title: "x > 3",
      intervals: [{ start: 3, end: null, start_inclusive: false, end_inclusive: false }],
    });
    const { getByTestId } = await render(<FunctionGraphBlock content={content} />);

    expect(getByTestId("skia-number-line-canvas")).toBeOnTheScreen();
  });

  it("uses Skia for a two-dimensional inequality", async () => {
    const content = JSON.stringify({
      type: "inequality",
      expr: "x + y <= 2",
      title: "x + y <= 2",
      comparator: "<=",
      a: 1,
      b: 1,
      c: 2,
      x_min: -5,
      x_max: 5,
      y_min: -5,
      y_max: 5,
      points: [],
    });
    const { getByTestId } = await render(<FunctionGraphBlock content={content} />);

    expect(getByTestId("skia-inequality-canvas")).toBeOnTheScreen();
  });
});

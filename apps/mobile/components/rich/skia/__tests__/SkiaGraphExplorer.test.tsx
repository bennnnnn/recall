import { render } from "@testing-library/react-native";

import type { GraphPoints } from "@/components/rich/graphPoints";
import { SkiaGraphCanvas } from "@/components/rich/skia/SkiaGraphExplorer";
import type { DrawnSeries } from "@/hooks/useInteractiveGraph";
import { useSkiaGraphViewport } from "@/hooks/useSkiaGraphViewport";
import { lightTheme } from "@/lib/theme";

const BOUNDS = { xMin: -6, xMax: 6, yMin: -4, yMax: 4 };

function series(partial: Partial<DrawnSeries>): DrawnSeries {
  return {
    id: "0",
    expr: "y = x^2",
    visible: true,
    locked: true,
    color: "#2563eb",
    points: [
      [-2, 4],
      [0, 0],
      [2, 4],
    ],
    invalid: false,
    cmp: "=",
    ...partial,
  };
}

function Harness({
  drawn,
  verticalX,
  points,
}: {
  drawn: DrawnSeries[];
  verticalX?: number;
  points?: GraphPoints;
}) {
  const viewport = useSkiaGraphViewport({
    width: 320,
    height: 240,
    pad: 28,
    initialView: BOUNDS,
    onCommit: () => {},
  });
  return (
    <SkiaGraphCanvas
      drawn={drawn}
      verticalX={verticalX}
      points={points}
      width={320}
      height={240}
      pad={28}
      theme={lightTheme}
      viewport={viewport}
    />
  );
}

describe("SkiaGraphCanvas", () => {
  it("renders the canvas for a function series", async () => {
    const { getByTestId } = await render(<Harness drawn={[series({})]} />);
    expect(getByTestId("skia-graph-canvas")).toBeTruthy();
  });

  it("draws holes and the fence's labelled marks without crashing", async () => {
    const points: GraphPoints = {
      holes: [{ point: [1, 2], color: "#2563eb" }],
      marks: [
        { point: [1, 0], color: "#2563eb", label: "(1, 0)" },
        { point: [5.9, 3.9], color: "#2563eb", label: "(5.9, 3.9)" },
      ],
    };
    // The mocked Canvas draws no children; the drawing itself is markLabelW's (graphWorklets).
    const { getByTestId } = await render(<Harness drawn={[series({})]} points={points} />);
    expect(getByTestId("skia-graph-canvas")).toBeTruthy();
  });

  it("renders inequality fills, hidden series, and a vertical line", async () => {
    const { getByTestId } = await render(
      <Harness
        verticalX={3}
        drawn={[
          series({ cmp: "<=" }),
          series({ id: "1", visible: false, locked: false }),
        ]}
      />,
    );
    expect(getByTestId("skia-graph-canvas")).toBeTruthy();
  });

  it("renders scatter markers and an active trace without crashing", async () => {
    // Hand-built viewport: the gesture is ignored by the mocked
    // GestureDetector, and the shared values start mid-trace.
    const viewport = {
      bounds: { value: BOUNDS },
      gesture: {},
      traceActive: { value: true },
      tracePos: { value: { px: 160, py: 120 } },
    } as unknown as ReturnType<typeof useSkiaGraphViewport>;
    const { getByTestId } = await render(
      <SkiaGraphCanvas
        drawn={[series({ points: [[1, 1], [2, 4]] as [number, number][] })]}
        width={320}
        height={240}
        pad={28}
        theme={lightTheme}
        viewport={viewport}
      />,
    );
    expect(getByTestId("skia-graph-canvas")).toBeTruthy();
  });
});

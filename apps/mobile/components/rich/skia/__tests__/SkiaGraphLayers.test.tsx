import { render } from "@testing-library/react-native";

import { SkiaGraphLayers } from "@/components/rich/skia/SkiaGraphLayers";
import { lightTheme } from "@/lib/theme";

const BOUNDS = { xMin: -6, xMax: 6, yMin: -4, yMax: 4 };

describe("SkiaGraphLayers", () => {
  it("draws regions, lines and the axis a region turns about without crashing", async () => {
    const layers = {
      lines: [
        { start: [-6, 0] as [number, number], end: [6, 0] as [number, number], role: "axis" as const, color: 0 },
        { start: [2, -4] as [number, number], end: [2, 4] as [number, number], role: "asymptote" as const, color: 0 },
      ],
      regions: [
        { points: [[0, 0], [1, 1], [1, 0]] as [number, number][], kind: "shade" as const, color: 0 },
        { points: [[0, -1], [0, -2], [0.1, -2]] as [number, number][], kind: "mirror" as const, color: 3 },
      ],
    };
    const frame = { bounds: { value: BOUNDS }, width: 320, height: 220, pad: 16 } as unknown as Parameters<
      typeof SkiaGraphLayers
    >[0]["frame"];
    const { getByTestId } = await render(<SkiaGraphLayers layers={layers} frame={frame} theme={lightTheme} />);
    expect(getByTestId("skia-plot-layers")).toBeTruthy();
  });
});

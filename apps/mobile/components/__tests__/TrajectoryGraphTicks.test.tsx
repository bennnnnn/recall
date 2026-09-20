import { expandBoundsForAxes, graphBounds } from "@/lib/math/graphBlock";
import { trajectoryAxisLayout } from "@/lib/math/trajectory";

describe("native physics trajectory time labels", () => {
  it.each([
    { end: 2.1, points: [[0, 20], [1, 15], [2, 0], [2.1, 0]], labels: ["0.5", "1", "1.5", "2"] },
    { end: 1.05, points: [[0, 20], [0.5, 18.75], [1, 15], [1.05, 14.4875]], labels: ["0.2", "0.4", "0.6", "0.8", "1"] },
  ])("places accurate time labels on the 0–$end second viewport", ({ end, points, labels }) => {
    const bounds = expandBoundsForAxes(graphBounds(points as [number, number][]), { pad: false });
    const layout = trajectoryAxisLayout(bounds, 342, 220, 28);

    expect(layout.xTicks.map((tick) => tick.text)).toEqual(labels);
    for (const tick of layout.xTicks) {
      expect(tick.py).toBe(208);
      const timeAtCoordinate = (tick.px - 28) * end / (342 - 56);
      expect(timeAtCoordinate).toBeCloseTo(Number(tick.text), 10);
    }
  });
});

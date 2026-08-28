import {
  CHART_MAX_HEIGHT,
  CHART_MIN_HEIGHT,
  clampChartPreviewHeight,
  nextChartPreviewHeight,
} from "@/lib/chartPreviewHeight";

describe("clampChartPreviewHeight", () => {
  it("floors empty reports at the min placeholder", () => {
    expect(clampChartPreviewHeight(0, CHART_MAX_HEIGHT)).toBe(CHART_MIN_HEIGHT);
  });

  it("caps at the active max", () => {
    expect(clampChartPreviewHeight(900, CHART_MAX_HEIGHT)).toBe(CHART_MAX_HEIGHT);
  });
});

describe("nextChartPreviewHeight", () => {
  it("grows from the placeholder toward the reported SVG height", () => {
    expect(nextChartPreviewHeight(240, CHART_MIN_HEIGHT, CHART_MAX_HEIGHT)).toBe(240);
  });

  it("does not shrink after first paint", () => {
    expect(nextChartPreviewHeight(160, 300, CHART_MAX_HEIGHT)).toBeNull();
  });
});

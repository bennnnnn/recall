import {
  MAX_REGION_RATIO,
  MIN_REGION_RATIO,
  clampScanRegion,
  defaultScanRegion,
  regionToImageCrop,
  scaleScanRegion,
  translateScanRegion,
} from "@/lib/mathScannerRegion";

describe("defaultScanRegion", () => {
  it("is centered and within bounds", () => {
    const region = defaultScanRegion();
    expect(region.x + region.width / 2).toBeCloseTo(0.5, 5);
    expect(region.y + region.height / 2).toBeCloseTo(0.5, 5);
    expect(region.width).toBeGreaterThanOrEqual(MIN_REGION_RATIO);
    expect(region.height).toBeGreaterThanOrEqual(MIN_REGION_RATIO);
  });
});

describe("clampScanRegion", () => {
  it("clamps size to [MIN_REGION_RATIO, MAX_REGION_RATIO]", () => {
    const tooSmall = clampScanRegion({ x: 0.5, y: 0.5, width: 0.01, height: 0.01 });
    expect(tooSmall.width).toBe(MIN_REGION_RATIO);
    expect(tooSmall.height).toBe(MIN_REGION_RATIO);

    const tooBig = clampScanRegion({ x: 0, y: 0, width: 5, height: 5 });
    expect(tooBig.width).toBe(MAX_REGION_RATIO);
    expect(tooBig.height).toBe(MAX_REGION_RATIO);
  });

  it("keeps the region fully on-screen (0..1) by clamping position", () => {
    const offLeft = clampScanRegion({ x: -0.5, y: -0.5, width: 0.4, height: 0.3 });
    expect(offLeft.x).toBe(0);
    expect(offLeft.y).toBe(0);

    const offRight = clampScanRegion({ x: 0.9, y: 0.9, width: 0.4, height: 0.3 });
    expect(offRight.x).toBe(0.6); // 1 - width
    expect(offRight.y).toBe(0.7); // 1 - height
  });
});

describe("scaleScanRegion", () => {
  it("resizes around the region's own center", () => {
    const base = { x: 0.3, y: 0.4, width: 0.4, height: 0.2 };
    const scaled = scaleScanRegion(base, 2);
    const baseCx = base.x + base.width / 2;
    const baseCy = base.y + base.height / 2;
    expect(scaled.width).toBeCloseTo(0.8, 5);
    expect(scaled.height).toBeCloseTo(0.4, 5);
    expect(scaled.x + scaled.width / 2).toBeCloseTo(baseCx, 5);
    expect(scaled.y + scaled.height / 2).toBeCloseTo(baseCy, 5);
  });

  it("re-clamps after scaling so it never grows off-screen", () => {
    const base = { x: 0.4, y: 0.4, width: 0.3, height: 0.3 };
    const scaled = scaleScanRegion(base, 10);
    expect(scaled.width).toBeLessThanOrEqual(MAX_REGION_RATIO);
    expect(scaled.x).toBeGreaterThanOrEqual(0);
    expect(scaled.x + scaled.width).toBeLessThanOrEqual(1);
  });
});

describe("translateScanRegion", () => {
  it("moves the region by a ratio delta", () => {
    const base = { x: 0.3, y: 0.3, width: 0.2, height: 0.2 };
    const moved = translateScanRegion(base, 0.1, -0.05);
    expect(moved.x).toBeCloseTo(0.4, 5);
    expect(moved.y).toBeCloseTo(0.25, 5);
    expect(moved.width).toBe(base.width);
    expect(moved.height).toBe(base.height);
  });

  it("stops at the screen edge instead of moving off-screen", () => {
    const base = { x: 0.05, y: 0.05, width: 0.3, height: 0.3 };
    const moved = translateScanRegion(base, -0.5, -0.5);
    expect(moved.x).toBe(0);
    expect(moved.y).toBe(0);
  });
});

describe("regionToImageCrop", () => {
  it("maps a ratio region to pixel coordinates on the actual photo", () => {
    const crop = regionToImageCrop({ x: 0.25, y: 0.1, width: 0.5, height: 0.3 }, 1000, 2000);
    expect(crop).toEqual({ originX: 250, originY: 200, width: 500, height: 600 });
  });

  it("never produces a crop that overflows the image bounds", () => {
    // A region ratio right at the edge should still round-trip to a crop
    // that fits inside the actual photo dimensions.
    const crop = regionToImageCrop({ x: 0.9, y: 0.9, width: 0.3, height: 0.3 }, 1000, 1000);
    expect(crop.originX + crop.width).toBeLessThanOrEqual(1000);
    expect(crop.originY + crop.height).toBeLessThanOrEqual(1000);
  });

  it("always produces at least a 1px crop even for a degenerate region", () => {
    const crop = regionToImageCrop({ x: 1, y: 1, width: 0.001, height: 0.001 }, 100, 100);
    expect(crop.width).toBeGreaterThanOrEqual(1);
    expect(crop.height).toBeGreaterThanOrEqual(1);
  });
});

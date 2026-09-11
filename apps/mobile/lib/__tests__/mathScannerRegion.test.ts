import {
  FOCUS_SQUARE_SIZE,
  MAX_REGION_RATIO,
  MIN_REGION_RATIO,
  clampCameraZoom,
  clampFocusInRegion,
  clampScanRegion,
  defaultScanRegion,
  regionIsDefault,
  regionToImageCrop,
  resizeScanRegionFromCorner,
  scaleScanRegion,
  translateScanRegion,
  zoomFromPinch,
} from "@/lib/math/mathScannerRegion";

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

describe("resizeScanRegionFromCorner", () => {
  it("grows the bottom-right corner while keeping the opposite corner", () => {
    const base = { x: 0.2, y: 0.2, width: 0.4, height: 0.3 };
    const resized = resizeScanRegionFromCorner(base, "br", 0.1, 0.05);
    expect(resized.x).toBeCloseTo(0.2, 5);
    expect(resized.y).toBeCloseTo(0.2, 5);
    expect(resized.width).toBeCloseTo(0.5, 5);
    expect(resized.height).toBeCloseTo(0.35, 5);
  });

  it("shrinks from the top-left without inverting the rectangle", () => {
    const base = { x: 0.3, y: 0.3, width: 0.4, height: 0.4 };
    const resized = resizeScanRegionFromCorner(base, "tl", 0.2, 0.2);
    expect(resized.width).toBeGreaterThanOrEqual(MIN_REGION_RATIO);
    expect(resized.height).toBeGreaterThanOrEqual(MIN_REGION_RATIO);
    expect(resized.x + resized.width).toBeCloseTo(0.7, 5);
    expect(resized.y + resized.height).toBeCloseTo(0.7, 5);
  });

  it("stays fully on-screen when a corner is dragged off the edge", () => {
    const base = { x: 0.1, y: 0.1, width: 0.4, height: 0.4 };
    const resized = resizeScanRegionFromCorner(base, "tl", -0.5, -0.5);
    expect(resized.x).toBe(0);
    expect(resized.y).toBe(0);
    expect(resized.x + resized.width).toBeLessThanOrEqual(1);
    expect(resized.y + resized.height).toBeLessThanOrEqual(1);
  });
});

describe("regionIsDefault", () => {
  it("is true for the default region and false after a move", () => {
    expect(regionIsDefault(defaultScanRegion())).toBe(true);
    expect(regionIsDefault(translateScanRegion(defaultScanRegion(), 0.1, 0))).toBe(false);
  });
});

describe("clampCameraZoom / zoomFromPinch", () => {
  it("clamps zoom to 0..1", () => {
    expect(clampCameraZoom(-0.2)).toBe(0);
    expect(clampCameraZoom(1.4)).toBe(1);
    expect(clampCameraZoom(0.25)).toBe(0.25);
    expect(clampCameraZoom(Number.NaN)).toBe(0);
  });

  it("maps pinch scale onto zoom without jumping to 1 on a small pinch", () => {
    expect(zoomFromPinch(0, 1)).toBe(0);
    expect(zoomFromPinch(0, 1.4)).toBeCloseTo(0.2, 5);
    expect(zoomFromPinch(0.8, 0.2)).toBe(0.4);
    expect(zoomFromPinch(0.9, 3)).toBe(1);
  });
});

describe("clampFocusInRegion", () => {
  it("keeps the focus-square center inside the crop", () => {
    const next = clampFocusInRegion(10, 12, 300, 160);
    expect(next).toEqual({ x: FOCUS_SQUARE_SIZE / 2, y: FOCUS_SQUARE_SIZE / 2, size: FOCUS_SQUARE_SIZE });
  });

  it("ignores taps outside the crop", () => {
    expect(clampFocusInRegion(-1, 10, 300, 160)).toBeNull();
    expect(clampFocusInRegion(10, 400, 300, 160)).toBeNull();
  });

  it("shrinks the square when the crop is narrower than the default", () => {
    const next = clampFocusInRegion(20, 20, 40, 200);
    expect(next).not.toBeNull();
    expect(next?.size).toBe(40);
    expect(next?.x).toBe(20);
    expect((next?.x ?? 0) - (next?.size ?? 0) / 2).toBeGreaterThanOrEqual(0);
    expect((next?.x ?? 0) + (next?.size ?? 0) / 2).toBeLessThanOrEqual(40);
  });
});

describe("regionToImageCrop", () => {
  it("maps a ratio region to pixel coordinates on the actual photo", () => {
    const crop = regionToImageCrop({ x: 0.25, y: 0.1, width: 0.5, height: 0.3 }, 1000, 2000);
    expect(crop).toEqual({ originX: 250, originY: 200, width: 500, height: 600 });
  });

  it("BUG FIX regression: cover-scale crop accounts for letterboxing when aspects differ", () => {
    // Wide photo in a tall window: cover scales by height, crops the
    // horizontal overflow. A centered full-width overlay is not the
    // full image width.
    const crop = regionToImageCrop(
      { x: 0, y: 0.4, width: 1, height: 0.2 },
      2000,
      1000,
      400,
      800,
    );
    const naive = regionToImageCrop({ x: 0, y: 0.4, width: 1, height: 0.2 }, 2000, 1000);
    expect(crop.originX).toBeGreaterThan(0);
    expect(crop.originX).not.toBe(naive.originX);
    expect(crop.width).toBeLessThan(naive.width);
    expect(crop.originX + crop.width).toBeLessThanOrEqual(2000);
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

import { isLowLightExif } from "@/lib/scanner/lowLight";

describe("scanner low-light detection", () => {
  it("uses native EXIF brightness when available", () => {
    expect(isLowLightExif({ BrightnessValue: 0.4 })).toBe(true);
    expect(isLowLightExif({ BrightnessValue: 4.2 })).toBe(false);
  });

  it("supports nested exposure metadata and rational values", () => {
    expect(isLowLightExif({ Exif: { ExposureTime: "1/15", ISOSpeedRatings: [800] } })).toBe(true);
    expect(isLowLightExif({ ExposureTime: "1/120", PhotographicSensitivity: 100 })).toBe(false);
  });

  it("does not guess when the camera publishes no exposure reading", () => {
    expect(isLowLightExif(undefined)).toBeNull();
    expect(isLowLightExif({ Orientation: 1 })).toBeNull();
  });
});

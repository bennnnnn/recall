import { scanPhotoOptions } from "@/features/scanner/model/scanPhoto";

it("takes the scan's photo without a shutter sound or flash", () => {
  expect(scanPhotoOptions(true)).toEqual({
    flashMode: "off",
    enableShutterSound: false,
    enableDistortionCorrection: true,
  });
  expect(scanPhotoOptions(false).enableDistortionCorrection).toBe(false);
});

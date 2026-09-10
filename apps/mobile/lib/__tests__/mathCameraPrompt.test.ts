import {
  MATH_CAMERA_CONFIRMED_PREFIX,
  MATH_CAMERA_PROMPT,
  composerTextAfterMathScan,
  composerTextAfterMathScanConfirm,
  isMathCameraPrompt,
} from "@/lib/mathCameraPrompt";

describe("composerTextAfterMathScan", () => {
  it("uses the scan prompt when the composer is empty", () => {
    expect(composerTextAfterMathScan("")).toBe(MATH_CAMERA_PROMPT);
    expect(composerTextAfterMathScan("   ")).toBe(MATH_CAMERA_PROMPT);
  });

  it("keeps existing composer text instead of wiping it", () => {
    expect(composerTextAfterMathScan("already wrote this")).toBe("already wrote this");
    expect(composerTextAfterMathScan("  keep spaces around  ")).toBe("  keep spaces around  ");
  });
});

describe("isMathCameraPrompt", () => {
  it("matches the protocol caption and confirmed-reading follow-on", () => {
    expect(isMathCameraPrompt(MATH_CAMERA_PROMPT)).toBe(true);
    expect(isMathCameraPrompt(MATH_CAMERA_PROMPT.toUpperCase())).toBe(true);
    expect(isMathCameraPrompt(composerTextAfterMathScanConfirm("2x + 7 = 15"))).toBe(true);
    expect(isMathCameraPrompt("What's in this image?")).toBe(false);
  });
});

describe("composerTextAfterMathScanConfirm", () => {
  it("keeps the camera prompt when the reading is empty", () => {
    expect(composerTextAfterMathScanConfirm("")).toBe(MATH_CAMERA_PROMPT);
    expect(composerTextAfterMathScanConfirm("   ")).toBe(MATH_CAMERA_PROMPT);
  });

  it("appends the confirmed-reading protocol line", () => {
    expect(composerTextAfterMathScanConfirm("2x + 7 = 15")).toBe(
      `${MATH_CAMERA_PROMPT}\n\n${MATH_CAMERA_CONFIRMED_PREFIX} 2x + 7 = 15`,
    );
  });
});


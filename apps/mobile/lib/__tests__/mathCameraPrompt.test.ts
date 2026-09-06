import { MATH_CAMERA_PROMPT, composerTextAfterMathScan } from "@/lib/mathCameraPrompt";

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

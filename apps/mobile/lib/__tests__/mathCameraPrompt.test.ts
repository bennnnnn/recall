import {
  MATH_CAMERA_PROMPT,
  composerTextAfterMathScan,
  isMathCameraPrompt,
  mathScanSolveMessage,
} from "@/lib/math/cameraPrompt";
import { composerTextAfterScanConfirm } from "@/lib/scanner/readBack";

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
    expect(isMathCameraPrompt(composerTextAfterScanConfirm("2x + 7 = 15", "math"))).toBe(true);
    expect(isMathCameraPrompt("What's in this image?")).toBe(false);
  });
});

describe("mathScanSolveMessage", () => {
  it("asks for steps on the confirmed reading", () => {
    expect(mathScanSolveMessage("2x + 3 = 11")).toBe("Show steps: 2x + 3 = 11");
  });

  it("joins a system's lines into one problem", () => {
    expect(mathScanSolveMessage("x + y = 5\n x - y = 1\n")).toBe("Show steps: x + y = 5, x - y = 1");
    expect(mathScanSolveMessage("-2x \u2265 6\nx + 1 < 4")).toBe("Show steps: -2x \u2265 6, x + 1 < 4");
  });

  it("keeps a word problem's lines as one sentence run", () => {
    expect(mathScanSolveMessage("Tickets cost $5.\nHow many adults went?")).toBe(
      "Show steps: Tickets cost $5. How many adults went?",
    );
  });

  it("sends nothing for an empty reading", () => {
    expect(mathScanSolveMessage(" \n ")).toBe("");
  });
});

import {
  BIOLOGY_CAMERA_PROMPT,
  PHYSICS_CAMERA_PROMPT,
  composerTextAfterSubjectScan,
  isScannerCameraPrompt,
  scannerCameraPrompt,
} from "@/lib/scanner/subjects";

describe("scanner subjects", () => {
  it("maps each subject to a distinct protocol prompt", () => {
    expect(scannerCameraPrompt("math")).toContain("math problem");
    expect(scannerCameraPrompt("physics")).toBe(PHYSICS_CAMERA_PROMPT);
    expect(scannerCameraPrompt("biology")).toBe(BIOLOGY_CAMERA_PROMPT);
  });

  it("recognizes all scanner prompts without claiming normal image questions", () => {
    expect(isScannerCameraPrompt(PHYSICS_CAMERA_PROMPT)).toBe(true);
    expect(isScannerCameraPrompt(BIOLOGY_CAMERA_PROMPT.toUpperCase())).toBe(true);
    expect(isScannerCameraPrompt("What's in this image?")).toBe(false);
  });

  it("always carries the selected subject while preserving a typed caption", () => {
    expect(composerTextAfterSubjectScan("", "physics")).toBe(PHYSICS_CAMERA_PROMPT);
    expect(composerTextAfterSubjectScan("my own caption", "biology")).toBe(
      `${BIOLOGY_CAMERA_PROMPT}\n\nmy own caption`,
    );
  });
});

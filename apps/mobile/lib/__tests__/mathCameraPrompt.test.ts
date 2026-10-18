import { mathScanSolveMessage } from "@/lib/math/cameraPrompt";

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

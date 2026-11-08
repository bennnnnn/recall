import { hasUsefulScannerText, nextLiveRead, sameLiveText, STABLE_READS } from "@/features/scanner/model/liveText";

describe("live scanner text", () => {
  it("treats a formula as ready even when it has no digit", () => {
    expect(hasUsefulScannerText("NaCl")).toBe(true);
    expect(hasUsefulScannerText("H2O")).toBe(true);
    expect(hasUsefulScannerText("CO2")).toBe(true);
  });

  it("still ignores a short ordinary word", () => {
    expect(hasUsefulScannerText("OK")).toBe(false);
    expect(hasUsefulScannerText("Hi")).toBe(false);
    expect(hasUsefulScannerText("water")).toBe(false);
  });

  it("counts a question in words for physics, chemistry and biology, not for maths", () => {
    const question = "Explain how enzymes speed up reactions";
    expect(hasUsefulScannerText(question, "biology")).toBe(true);
    expect(hasUsefulScannerText("Why is the sky blue", "physics")).toBe(true);
    expect(hasUsefulScannerText("Name this compound please", "chemistry")).toBe(true);
    expect(hasUsefulScannerText(question, "math")).toBe(false);
    expect(hasUsefulScannerText("Cell biology", "biology")).toBe(false);
  });
});

describe("holding the frame steady", () => {
  it("takes a line read a little differently frame to frame as the same text", () => {
    expect(sameLiveText("2x+3=7", "2x+3=7.")).toBe(true);
    expect(sameLiveText("solve 2x + 3 = 7", "solve 2x +3 = 7")).toBe(true);
    expect(sameLiveText("2x+3=7", "y=mx+b")).toBe(false);
  });

  it("calls the frame ready after three reads of the same text, even when they differ a little", () => {
    const reads = ["Solve 2x + 3 = 7", "Solve 2x +3 = 7", "Solve 2x + 3 = 7."];
    let state = { text: "", count: 0 };
    const stable = reads.map((raw) => {
      const next = nextLiveRead(state, raw, "math");
      state = next.state;
      return next.stable;
    });
    expect(stable).toEqual([false, false, true]);
    expect(STABLE_READS).toBe(3);
  });

  it("starts over on new text, and on a frame with nothing useful", () => {
    let next = nextLiveRead({ text: "2x+3=7", count: 2 }, "y = mx + b", "math");
    expect(next.state.count).toBe(1);
    next = nextLiveRead(next.state, "hello", "math");
    expect(next).toEqual({ state: { text: "", count: 0 }, hasText: false, stable: false });
  });
});

import { shouldPushKeyboardHeight } from "@/lib/keyboardInset";

describe("shouldPushKeyboardHeight", () => {
  it("suppresses small sub-threshold deltas against the last pushed height", () => {
    expect(shouldPushKeyboardHeight(320, 300, 48, 310)).toBe(false);
  });

  it("pushes once the delta from last push reaches the threshold", () => {
    expect(shouldPushKeyboardHeight(348, 300, 48, 320)).toBe(true);
  });

  it("pushes the settled height even when the last step is under the threshold", () => {
    expect(shouldPushKeyboardHeight(336, 300, 48, 336)).toBe(true);
  });

  it("always pushes when the keyboard transitions from closed to open", () => {
    expect(shouldPushKeyboardHeight(1, 0, 4)).toBe(true);
  });

  it("always pushes when the keyboard transitions from open to closed", () => {
    expect(shouldPushKeyboardHeight(0, 1, 4)).toBe(true);
  });

  it("suppresses no-op repeats at the same height", () => {
    expect(shouldPushKeyboardHeight(300, 300, 4)).toBe(false);
  });
});

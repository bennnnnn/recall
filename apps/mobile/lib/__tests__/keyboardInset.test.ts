import { shouldPushKeyboardHeight } from "@/lib/keyboardInset";

describe("shouldPushKeyboardHeight", () => {
  it("suppresses small sub-threshold deltas", () => {
    expect(shouldPushKeyboardHeight(302, 300, 4)).toBe(false);
  });

  it("pushes once the delta reaches the threshold", () => {
    expect(shouldPushKeyboardHeight(305, 300, 4)).toBe(true);
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

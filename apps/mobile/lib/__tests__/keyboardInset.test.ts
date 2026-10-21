import { keyboardLiftAbove, settledKeyboardHeight } from "@/lib/keyboardInset";

const UNKNOWN = 0;
const OPENING = 1;
const OPEN = 2;
const CLOSING = 3;
const CLOSED = 4;

describe("settledKeyboardHeight", () => {
  it.each([
    [UNKNOWN, 0],
    [OPENING, 120],
    [CLOSING, 200],
  ])("holds React state while the keyboard moves (state %i)", (state, height) => {
    expect(settledKeyboardHeight(state, height)).toBeNull();
  });

  it("commits the height the keyboard opened to", () => {
    expect(settledKeyboardHeight(OPEN, 336)).toBe(336);
  });

  it("commits zero once the keyboard has closed, whatever the last frame said", () => {
    expect(settledKeyboardHeight(CLOSED, 12)).toBe(0);
  });

  it("never commits a negative height", () => {
    expect(settledKeyboardHeight(OPEN, -4)).toBe(0);
  });
});

describe("keyboardLiftAbove", () => {
  it("raises the composer by the keyboard less the resting bottom pad", () => {
    expect(keyboardLiftAbove(336, 34)).toBe(302);
  });

  it.each([0, 20, 34])("keeps the composer at rest while the keyboard is below the pad (%i)", (height) => {
    expect(keyboardLiftAbove(height, 34)).toBe(0);
  });
});

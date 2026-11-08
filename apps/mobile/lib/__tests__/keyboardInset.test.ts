import {
  correctedKeyboardHeight,
  keyboardCorrection,
  keyboardEventHeight,
  keyboardLiftAbove,
  NO_KEYBOARD_CORRECTION,
  settledKeyboardHeight,
  shouldPushKeyboardHeight,
} from "@/lib/keyboardInset";

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

describe("keyboardEventHeight", () => {
  it("measures an Android keyboard from the screen's bottom edge, the navigation bar included", () => {
    expect(keyboardEventHeight(252, 48)).toBe(300);
  });

  it.each([0, -48])("reads a keyboard that covers no bottom edge as down (%i)", (height) => {
    expect(keyboardEventHeight(height, 48)).toBe(0);
  });
});

describe("keyboardCorrection", () => {
  it("puts down a keyboard Reanimated still holds up after it closed", () => {
    expect(keyboardCorrection(300, 0)).toBe(0);
  });

  it("puts down one stopped part of the way through its hide", () => {
    expect(keyboardCorrection(137, 0)).toBe(0);
  });

  it("lifts the composer onto a keyboard Reanimated never saw rise", () => {
    expect(keyboardCorrection(0, 300)).toBe(300);
  });

  it.each([
    [0, 0],
    [300, 300],
    // Two readings of an open keyboard that differ stay Reanimated's: it measures the inset itself.
    [300, 296],
    [336, 300],
  ])("leaves Reanimated's keyboard alone when it agrees with the real one (%i, %i)", (reported, real) => {
    expect(keyboardCorrection(reported, real)).toBeNull();
  });

  it("corrects nothing before the first keyboard event", () => {
    expect(keyboardCorrection(300, null)).toBeNull();
  });

  it("puts down a keyboard Reanimated stopped following on the way down", () => {
    expect(keyboardCorrection(137, 0, { rose: false, fell: true })).toBe(0);
  });

  it("trusts Reanimated rising after the last hide: it follows a show whose event has not come", () => {
    expect(keyboardCorrection(300, 0, { rose: true, fell: false })).toBeNull();
  });

  it("trusts Reanimated falling after the last show: it follows a hide whose event has not come", () => {
    expect(keyboardCorrection(0, 300, { rose: true, fell: true })).toBeNull();
  });
});

describe("correctedKeyboardHeight", () => {
  it("draws Reanimated's height while no correction holds", () => {
    expect(correctedKeyboardHeight(300, NO_KEYBOARD_CORRECTION, 0)).toBe(300);
  });

  it("draws the real keyboard while Reanimated keeps reporting the stale height", () => {
    expect(correctedKeyboardHeight(300, 300, 0)).toBe(0);
    expect(correctedKeyboardHeight(0, 0, 300)).toBe(300);
  });

  it("follows Reanimated again the moment it reports anything else", () => {
    expect(correctedKeyboardHeight(120, 300, 0)).toBe(120);
  });

  it("never draws a negative height", () => {
    expect(correctedKeyboardHeight(-4, NO_KEYBOARD_CORRECTION, 0)).toBe(0);
  });
});

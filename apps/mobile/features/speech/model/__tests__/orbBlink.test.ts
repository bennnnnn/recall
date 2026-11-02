import {
  BLINK_CLOSE_MS,
  BLINK_OPEN_MS,
  nextBlinkGapMs,
  scheduleBlinks,
} from "@/features/speech/model/orbBlink";

describe("nextBlinkGapMs", () => {
  it.each([
    [0, 3000],
    [0.5, 4500],
    [1, 6000],
    [-1, 3000],
    [2, 6000],
  ])("maps random %s to %s ms, inside 3 to 6 s", (random, gap) => {
    expect(nextBlinkGapMs(() => random)).toBe(gap);
  });
});

describe("scheduleBlinks", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });
  afterEach(() => {
    jest.useRealTimers();
  });

  it("is a quick close and open", () => {
    expect(BLINK_CLOSE_MS + BLINK_OPEN_MS).toBeGreaterThanOrEqual(120);
    expect(BLINK_CLOSE_MS + BLINK_OPEN_MS).toBeLessThanOrEqual(180);
  });

  it("blinks after each freshly drawn gap, so the rhythm varies", () => {
    const draws = [0, 1, 0.5];
    const onBlink = jest.fn();
    const stop = scheduleBlinks(onBlink, () => draws.shift() ?? 0);

    jest.advanceTimersByTime(2999);
    expect(onBlink).not.toHaveBeenCalled();
    jest.advanceTimersByTime(1);
    expect(onBlink).toHaveBeenCalledTimes(1);
    // The second gap is the longest, 6 s: not a fixed beat.
    jest.advanceTimersByTime(5999);
    expect(onBlink).toHaveBeenCalledTimes(1);
    jest.advanceTimersByTime(1);
    expect(onBlink).toHaveBeenCalledTimes(2);
    jest.advanceTimersByTime(4500);
    expect(onBlink).toHaveBeenCalledTimes(3);
    stop();
  });

  it("never blinks again once stopped", () => {
    const onBlink = jest.fn();
    const stop = scheduleBlinks(onBlink, () => 0);
    jest.advanceTimersByTime(3000);
    stop();
    jest.advanceTimersByTime(60_000);
    expect(onBlink).toHaveBeenCalledTimes(1);
  });
});

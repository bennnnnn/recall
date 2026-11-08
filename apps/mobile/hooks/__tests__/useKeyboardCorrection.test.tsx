import { Keyboard, Platform, type KeyboardEvent } from "react-native";
import type { SharedValue } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { renderHook } from "@testing-library/react-native";

import { KEYBOARD_CHECK_MS, KEYBOARD_EVENT_TAIL_MS, useKeyboardCorrection } from "@/hooks/useKeyboardCorrection";
import { correctedKeyboardHeight, NO_KEYBOARD_CORRECTION } from "@/lib/keyboardInset";

/** The S23's 3-button navigation bar; React Native's events measure the keyboard above it. */
const NAV_BAR = 48;
/** The keyboard as Reanimated measures it, the bar included. */
const KEYBOARD = 300;

type Listener = (event: KeyboardEvent) => void;
const listeners = new Map<string, Set<Listener>>();

function keyboardEvent(name: "keyboardDidShow" | "keyboardDidHide", height = 0) {
  const event = { endCoordinates: { height, screenX: 0, screenY: 0, width: 0 } } as KeyboardEvent;
  for (const listener of listeners.get(name) ?? []) listener(event);
}

/** Reanimated's `keyboard.height`, which the test moves by hand. */
function reanimatedHeight(value: number) {
  return {
    value,
    get() {
      return this.value;
    },
    set(next: number) {
      this.value = next;
    },
  };
}

async function setup() {
  const reported = reanimatedHeight(0);
  const onCorrect = jest.fn();
  const hook = await renderHook(() =>
    useKeyboardCorrection(reported as unknown as SharedValue<number>, onCorrect),
  );
  const correction = () => hook.result.current;
  return {
    onCorrect,
    correction,
    /** The safe area reports a new navigation bar (gesture navigation turned on, a rotation). */
    async navigationBar(bottom: number) {
      jest.mocked(useSafeAreaInsets).mockReturnValue({ top: 0, left: 0, right: 0, bottom });
      await hook.rerender({});
    },
    /** One frame Reanimated reports; returns the height JS takes for it. */
    frame(height: number) {
      reported.value = height;
      return correction().onFrame(height);
    },
    /** What the composer is drawn against on the UI thread. */
    drawn() {
      const { heldAt, real } = correction();
      return correctedKeyboardHeight(reported.value, heldAt.value, real.value);
    },
    settle(ms = KEYBOARD_CHECK_MS) {
      jest.advanceTimersByTime(ms);
    },
  };
}

type KeyboardHarness = Awaited<ReturnType<typeof setup>>;

/** The keyboard opens, Reanimated following it frame by frame. */
function open(kb: KeyboardHarness) {
  keyboardEvent("keyboardDidShow", KEYBOARD - NAV_BAR);
  for (const height of [60, 180, KEYBOARD]) kb.frame(height);
  kb.settle();
}

describe("useKeyboardCorrection", () => {
  let platform: jest.ReplaceProperty<typeof Platform.OS>;

  beforeEach(() => {
    jest.useFakeTimers();
    platform = jest.replaceProperty(Platform, "OS", "android");
    jest.mocked(useSafeAreaInsets).mockReturnValue({ top: 0, left: 0, right: 0, bottom: NAV_BAR });
    listeners.clear();
    jest.spyOn(Keyboard, "addListener").mockImplementation(((name: string, listener: Listener) => {
      const set = listeners.get(name) ?? new Set();
      set.add(listener);
      listeners.set(name, set);
      return { remove: () => set.delete(listener) };
    }) as never);
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  it("leaves a show and a hide Reanimated follows alone", async () => {
    const kb = await setup();
    open(kb);
    keyboardEvent("keyboardDidHide");
    for (const height of [220, 90, 0]) kb.frame(height);
    kb.settle();

    expect(kb.onCorrect).not.toHaveBeenCalled();
    expect(kb.correction().heldAt.value).toBe(NO_KEYBOARD_CORRECTION);
    expect(kb.drawn()).toBe(0);
  });

  it("brings the composer down when the keyboard closed and Reanimated still holds it up", async () => {
    const kb = await setup();
    open(kb);
    // Back, a sheet or another app closed it: no frame follows the hide.
    keyboardEvent("keyboardDidHide");
    kb.settle(KEYBOARD_CHECK_MS - 1);
    expect(kb.drawn()).toBe(KEYBOARD);

    kb.settle(1);
    expect(kb.drawn()).toBe(0);
    expect(kb.onCorrect).toHaveBeenCalledTimes(1);
    expect(kb.onCorrect).toHaveBeenCalledWith(0);
    // A repeat of the stale frame (Reanimated's state flipping) keeps the composer down.
    expect(kb.frame(KEYBOARD)).toBe(0);
    kb.settle();
    expect(kb.onCorrect).toHaveBeenCalledTimes(1);
  });

  it("brings it down from a hide Reanimated stopped following part of the way", async () => {
    const kb = await setup();
    open(kb);
    keyboardEvent("keyboardDidHide");
    kb.frame(240);
    kb.frame(137);
    kb.settle();

    expect(kb.drawn()).toBe(0);
    expect(kb.onCorrect).toHaveBeenCalledWith(0);
  });

  it("waits while Reanimated is still moving", async () => {
    const kb = await setup();
    open(kb);
    keyboardEvent("keyboardDidHide");
    for (const height of [280, 250, 210]) {
      kb.settle(KEYBOARD_CHECK_MS - 20);
      kb.frame(height);
    }

    expect(kb.onCorrect).not.toHaveBeenCalled();
    expect(kb.drawn()).toBe(210);
  });

  it("lets Reanimated lead again as soon as it reports another height", async () => {
    const kb = await setup();
    open(kb);
    keyboardEvent("keyboardDidHide");
    kb.settle();
    expect(kb.drawn()).toBe(0);

    // The keyboard opens again, to the very height that was stale: the first frame ends it.
    expect(kb.frame(70)).toBe(70);
    expect(kb.correction().heldAt.value).toBe(NO_KEYBOARD_CORRECTION);
    keyboardEvent("keyboardDidShow", KEYBOARD - NAV_BAR);
    expect(kb.frame(KEYBOARD)).toBe(KEYBOARD);
    kb.settle();
    expect(kb.drawn()).toBe(KEYBOARD);
    expect(kb.onCorrect).toHaveBeenCalledTimes(1);
  });

  it("glides back onto Reanimated when the keyboard comes back without it moving", async () => {
    const kb = await setup();
    open(kb);
    keyboardEvent("keyboardDidHide");
    kb.settle();
    expect(kb.drawn()).toBe(0);

    keyboardEvent("keyboardDidShow", KEYBOARD - NAV_BAR);
    // Held until the reading is checked: letting go at once could flash the stale height.
    expect(kb.drawn()).toBe(0);
    kb.settle();
    expect(kb.drawn()).toBe(KEYBOARD);
    expect(kb.onCorrect).toHaveBeenLastCalledWith(KEYBOARD);
    // JS holds nothing: the next frame is Reanimated's own.
    expect(kb.frame(KEYBOARD)).toBe(KEYBOARD);
  });

  it("brings React back down when a keyboard Reanimated never saw closes (a Modal sheet's field)", async () => {
    const kb = await setup();
    keyboardEvent("keyboardDidShow", KEYBOARD - NAV_BAR);
    kb.settle();
    expect(kb.drawn()).toBe(KEYBOARD);
    expect(kb.onCorrect).toHaveBeenLastCalledWith(KEYBOARD);

    keyboardEvent("keyboardDidHide");
    expect(kb.drawn()).toBe(KEYBOARD);
    kb.settle();
    expect(kb.drawn()).toBe(0);
    expect(kb.onCorrect).toHaveBeenLastCalledWith(0);
    expect(kb.onCorrect).toHaveBeenCalledTimes(2);
  });

  it("follows a keyboard that changes height without Reanimated following (the emoji panel)", async () => {
    const kb = await setup();
    open(kb);
    keyboardEvent("keyboardDidShow", 400 - NAV_BAR);
    kb.settle();

    expect(kb.drawn()).toBe(400);
    expect(kb.onCorrect).toHaveBeenCalledWith(400);
  });

  it("leaves an open keyboard a few points off the real one to Reanimated", async () => {
    const kb = await setup();
    open(kb);
    keyboardEvent("keyboardDidShow", KEYBOARD - NAV_BAR + 5.5);
    kb.settle();

    expect(kb.onCorrect).not.toHaveBeenCalled();
    expect(kb.drawn()).toBe(KEYBOARD);
  });

  it("lifts the composer onto a keyboard Reanimated never saw rise", async () => {
    const kb = await setup();
    keyboardEvent("keyboardDidShow", KEYBOARD - NAV_BAR);
    kb.settle();

    expect(kb.drawn()).toBe(KEYBOARD);
    expect(kb.onCorrect).toHaveBeenCalledWith(KEYBOARD);
  });

  it("trusts Reanimated over a show React Native has not reported yet", async () => {
    const kb = await setup();
    open(kb);
    keyboardEvent("keyboardDidHide");
    for (const height of [150, 0]) kb.frame(height);
    kb.settle();
    // The keyboard opens again and Reanimated follows it before keyboardDidShow arrives.
    for (const height of [90, KEYBOARD]) kb.frame(height);
    kb.settle();

    expect(kb.onCorrect).not.toHaveBeenCalled();
    expect(kb.drawn()).toBe(KEYBOARD);
  });

  it("trusts Reanimated over a hide React Native has not reported yet", async () => {
    const kb = await setup();
    open(kb);
    for (const height of [150, 0]) kb.frame(height);
    kb.settle();

    expect(kb.onCorrect).not.toHaveBeenCalled();
    expect(kb.drawn()).toBe(0);
  });

  it("keeps a pending check when the navigation bar changes, and measures against the new bar", async () => {
    const kb = await setup();
    keyboardEvent("keyboardDidShow", KEYBOARD - NAV_BAR);
    // Gesture navigation: a 24 pt bar, before the check for a keyboard Reanimated never saw.
    await kb.navigationBar(24);
    kb.settle();

    expect(kb.drawn()).toBe(KEYBOARD - NAV_BAR + 24);
    expect(kb.onCorrect).toHaveBeenCalledWith(KEYBOARD - NAV_BAR + 24);
  });

  it("still corrects a missed hide that arrives with a navigation bar change", async () => {
    const kb = await setup();
    open(kb);
    keyboardEvent("keyboardDidHide");
    await kb.navigationBar(24);
    kb.settle();

    expect(kb.drawn()).toBe(0);
    expect(kb.onCorrect).toHaveBeenCalledWith(0);
  });

  it("corrects a hide whose show was still rising when it came, then stopped part of the way", async () => {
    const kb = await setup();
    keyboardEvent("keyboardDidShow", KEYBOARD - NAV_BAR);
    kb.frame(60);
    kb.frame(180);
    keyboardEvent("keyboardDidHide");
    // The show's last frame reaches JS after the hide's event; then Reanimated stops.
    kb.frame(240);
    kb.settle();

    expect(kb.drawn()).toBe(0);
    expect(kb.onCorrect).toHaveBeenCalledWith(0);
  });

  it("still trusts a rise that starts well after the hide: a show whose event has not come", async () => {
    const kb = await setup();
    open(kb);
    keyboardEvent("keyboardDidHide");
    kb.settle(KEYBOARD_EVENT_TAIL_MS);
    for (const height of [90, KEYBOARD]) kb.frame(height);
    kb.settle();

    expect(kb.onCorrect).not.toHaveBeenCalled();
    expect(kb.drawn()).toBe(KEYBOARD);
  });

  it("changes nothing on iOS, where Reanimated tracks the keyboard itself", async () => {
    platform.replaceValue("ios");
    const kb = await setup();
    expect(listeners.size).toBe(0);
    expect(kb.frame(KEYBOARD)).toBe(KEYBOARD);
    kb.settle();

    expect(kb.onCorrect).not.toHaveBeenCalled();
    expect(kb.drawn()).toBe(KEYBOARD);
  });
});

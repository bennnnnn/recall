import { createRef } from "react";
import { Keyboard, Platform, type TextInputInstance } from "react-native";
import { act, renderHook } from "@testing-library/react-native";

import { focusForTyping, useMathPadField } from "@/features/chat/hooks/useMathPadField";

type Listener = () => void;
const listeners = new Map<string, Set<Listener>>();

function keyboardDidShow() {
  for (const listener of listeners.get("keyboardDidShow") ?? []) listener();
}

type FakeField = {
  focused: boolean;
  isFocused: jest.Mock<boolean, []>;
  focus: jest.Mock<void, []>;
  blur: jest.Mock<void, []>;
};

/** The composer's text field: focus as React Native's TextInputState tracks it. */
function fakeField(focused: boolean) {
  const field: FakeField = {
    focused,
    isFocused: jest.fn(() => field.focused),
    focus: jest.fn(() => {
      field.focused = true;
    }),
    blur: jest.fn(() => {
      field.focused = false;
    }),
  };
  const ref = createRef<TextInputInstance>() as { current: TextInputInstance | null };
  ref.current = field as unknown as TextInputInstance;
  return { field, ref };
}

async function renderPad(open: boolean, ref: { current: TextInputInstance | null }) {
  return renderHook(({ isOpen }: { isOpen: boolean }) => useMathPadField(isOpen, ref), {
    initialProps: { isOpen: open },
  });
}

describe("useMathPadField", () => {
  let platform: jest.ReplaceProperty<typeof Platform.OS>;

  beforeEach(() => {
    jest.useFakeTimers();
    platform = jest.replaceProperty(Platform, "OS", "android");
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

  describe("on Android", () => {
    it("never focuses the field while the pad is up, so the phone's keyboard cannot come up under it", async () => {
      const { field, ref } = fakeField(false);
      await renderPad(true, ref);
      await act(async () => {
        jest.runOnlyPendingTimers();
      });

      expect(field.focus).not.toHaveBeenCalled();
    });

    it("lets go of a field still focused when the pad opens", async () => {
      const { field, ref } = fakeField(true);
      await renderPad(true, ref);

      expect(field.blur).toHaveBeenCalledTimes(1);
      expect(field.focused).toBe(false);
    });

    it("puts down a phone keyboard that comes up for the field under the pad", async () => {
      const { field, ref } = fakeField(false);
      await renderPad(true, ref);
      field.focused = true;
      keyboardDidShow();

      expect(field.blur).toHaveBeenCalledTimes(1);
    });

    it("leaves a keyboard that belongs to another field", async () => {
      const { field, ref } = fakeField(false);
      await renderPad(true, ref);
      keyboardDidShow();

      expect(field.blur).not.toHaveBeenCalled();
    });

    it("stops watching the phone's keyboard once the pad closes", async () => {
      const { field, ref } = fakeField(false);
      const hook = await renderPad(true, ref);
      await hook.rerender({ isOpen: false });
      field.focused = true;
      keyboardDidShow();

      expect(field.blur).not.toHaveBeenCalled();
    });

    it("ABC lets go of a field focused under the pad before focusing it, which brings the keyboard up", () => {
      const { field, ref } = fakeField(true);
      focusForTyping(ref.current);

      expect(field.blur).toHaveBeenCalledTimes(1);
      expect(field.focus).toHaveBeenCalledTimes(1);
      expect(field.blur.mock.invocationCallOrder[0]).toBeLessThan(field.focus.mock.invocationCallOrder[0]);
    });

    it("ABC focuses a field that holds no focus at once", () => {
      const { field, ref } = fakeField(false);
      focusForTyping(ref.current);

      expect(field.blur).not.toHaveBeenCalled();
      expect(field.focus).toHaveBeenCalledTimes(1);
    });
  });

  describe("on iOS", () => {
    beforeEach(() => {
      platform.replaceValue("ios");
    });

    it("keeps the field focused under the pad's empty input view, as before", async () => {
      const { field, ref } = fakeField(false);
      await renderPad(true, ref);
      await act(async () => {
        jest.runOnlyPendingTimers();
      });

      expect(field.focus).toHaveBeenCalledTimes(1);
      expect(listeners.size).toBe(0);
    });

    it("ABC focuses the field without letting go: its keyboard swaps back in place", () => {
      const { field, ref } = fakeField(true);
      focusForTyping(ref.current);

      expect(field.blur).not.toHaveBeenCalled();
      expect(field.focus).toHaveBeenCalledTimes(1);
    });
  });
});

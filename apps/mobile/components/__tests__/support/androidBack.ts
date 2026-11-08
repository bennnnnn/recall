/**
 * Android's Back in Jest, where `BackHandler` is the iOS one and does nothing. Listeners are
 * asked newest first and the first that answers true ends it, as React Native does on
 * Android; `press()` says whether one did (false: Back would have left the screen).
 * Restore it with `jest.restoreAllMocks()`.
 */
import { BackHandler } from "react-native";

type Listener = () => boolean | null | undefined;

export function fakeAndroidBack() {
  const listeners: Listener[] = [];
  jest.spyOn(BackHandler, "addEventListener").mockImplementation((_event, handler) => {
    const listener: Listener = () => handler({} as never);
    listeners.push(listener);
    return {
      remove: () => {
        const at = listeners.indexOf(listener);
        if (at !== -1) listeners.splice(at, 1);
      },
    };
  });
  return {
    press(): boolean {
      for (let at = listeners.length - 1; at >= 0; at -= 1) {
        if (listeners[at]?.()) return true;
      }
      return false;
    },
    /** How many listeners are waiting for Back. */
    listening: () => listeners.length,
  };
}

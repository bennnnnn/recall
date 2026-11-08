import { createContext, useContext, useEffect, type ReactNode } from "react";
import { BackHandler } from "react-native";

import { useLatestRef } from "@/lib/latestRef";

/** Whether the screen around the caller is the one on top (`AndroidBackScreen`). */
const ScreenOnTop = createContext<() => boolean>(() => true);

/**
 * For a screen that stays mounted under the ones pushed over it (the chat, under Settings,
 * To-do and Memory): what it left open answers Back only while it is on top, so Back on the
 * screen above goes back instead of closing something nobody can see.
 */
export function AndroidBackScreen({ isOnTop, children }: { isOnTop: () => boolean; children: ReactNode }) {
  return <ScreenOnTop.Provider value={isOnTop}>{children}</ScreenOnTop.Provider>;
}

/**
 * Android Back closes what the user opened in the screen before it leaves the screen: a
 * sheet drawn in it, the drawer, the math pad, the full-height editor. A Modal gets Back
 * from the system; these are views in the screen, so Back went past them and sent the app
 * to the background.
 *
 * While `active`, Back calls `onBack` and goes no further. React Native asks the newest
 * listener first, and this one is added when `active` turns on (not again while it stays
 * on, whatever `onBack` is). So of two things opened one after the other, Back closes the
 * later first: a sheet over the math pad, the drawer over the composer. Two that turn on
 * in the same render are added in the order React runs their effects (a child before its
 * parent, then siblings in order), so the one drawn on top should sit later in the tree.
 * iOS has no Back button.
 */
export function useAndroidBack(active: boolean, onBack: () => void): void {
  const isOnTop = useContext(ScreenOnTop);
  const latest = useLatestRef({ isOnTop, onBack });
  useEffect(() => {
    if (!active) return;
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      if (!latest.current.isOnTop()) return false;
      latest.current.onBack();
      return true;
    });
    return () => sub.remove();
  }, [active, latest]);
}

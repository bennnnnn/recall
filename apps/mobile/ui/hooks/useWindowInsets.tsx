/**
 * The window's safe area, for a layer drawn over the whole window (a sheet, a menu, a
 * full-screen page). The screens sit in a frame of their own under the offline banner
 * (`OfflineFrame`), so their `useSafeAreaInsets()` is the frame's: no top inset while the
 * banner covers the status bar. A layer over the window still needs the window's.
 */
import { createContext, type ReactNode, useContext } from "react";
import { type EdgeInsets, SafeAreaInsetsContext, useSafeAreaInsets } from "react-native-safe-area-context";

const WindowInsetsContext = createContext<EdgeInsets | null>(null);

/** Above the screens' frame: names the window's insets for every layer under it. */
export function WindowInsetsProvider({ children }: { children: ReactNode }) {
  const insets = useSafeAreaInsets();
  return <WindowInsetsContext.Provider value={insets}>{children}</WindowInsetsContext.Provider>;
}

/** The window's insets; a tree with no frame (a test, a sheet's preview) reads its own. */
export function useWindowInsets(): EdgeInsets {
  const screen = useSafeAreaInsets();
  return useContext(WindowInsetsContext) ?? screen;
}

/** A full-window layer's content: `useSafeAreaInsets()` inside it is the window's again. */
export function WindowInsetsScope({ children }: { children: ReactNode }) {
  const insets = useWindowInsets();
  // A test that stands in for the library with its hook alone has no context to set.
  const Insets = SafeAreaInsetsContext as typeof SafeAreaInsetsContext | undefined;
  if (!Insets) return <>{children}</>;
  return <Insets.Provider value={insets}>{children}</Insets.Provider>;
}

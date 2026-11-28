import { useSafeAreaFrame } from "react-native-safe-area-context";

/**
 * The height the screens have: the window's, less the offline banner above them while it
 * shows (`OfflineFrame` gives the screens a safe-area provider of their own, whose frame
 * this is). A layout sized from the window was one banner too tall offline: the empty
 * chat scrolled and its last-chat card sat behind the composer.
 */
export function useScreenHeight(): number {
  return useSafeAreaFrame().height;
}

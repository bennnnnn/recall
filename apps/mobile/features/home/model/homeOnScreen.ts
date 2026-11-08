/**
 * Whether the home (an empty chat's greeting) is on screen. While it is, the composer's
 * placeholder reads "Ask Recall" instead of "Reply to Recall". The home sets it as it mounts
 * and unmounts; it holds no account's data.
 */
import { useSyncExternalStore } from "react";

import { createValueStore } from "@/lib/listenerSet";

export const homeOnScreen = createValueStore(false);

export function useHomeOnScreen(): boolean {
  return useSyncExternalStore(homeOnScreen.subscribe, homeOnScreen.get, homeOnScreen.get);
}

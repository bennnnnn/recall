/**
 * Whether the home (an empty chat's greeting) is on screen. While it is, the composer's
 * placeholder shows what to ask (`HOME_EXAMPLES`) instead of "Reply to Recall". The home sets
 * it as it mounts and unmounts; it holds no account's data.
 */
import { useSyncExternalStore } from "react";

import { createValueStore } from "@/lib/listenerSet";

export const homeOnScreen = createValueStore(false);

export function useHomeOnScreen(): boolean {
  return useSyncExternalStore(homeOnScreen.subscribe, homeOnScreen.get, homeOnScreen.get);
}

/** What the placeholder cycles through on the home, one every ``HOME_EXAMPLE_MS``. */
export const HOME_EXAMPLES = [
  "chat.home.example_scan",
  "chat.home.example_plan",
  "chat.home.example_explain",
  "chat.home.example_remind",
  "chat.home.example_write",
] as const;

export const HOME_EXAMPLE_MS = 3500;

/** Sync first-paint home content — no network, no `@/lib/api` import
 * (keeps HomeProvider free of circular-module init races with Metro). */

import i18n from "@/lib/i18n";
import type { HomeScreen } from "@/lib/api/types";

export function localGreeting(now: Date = new Date()): string {
  const hour = now.getHours();
  if (hour >= 5 && hour < 12) return i18n.t("chat.home.greeting_morning");
  if (hour >= 12 && hour < 17) return i18n.t("chat.home.greeting_afternoon");
  if (hour >= 17 && hour < 22) return i18n.t("chat.home.greeting_evening");
  return i18n.t("chat.home.greeting_night");
}

/** Sync placeholder so post-login home never paints a bare spinner. */
export function instantHomePlaceholder(now: Date = new Date()): HomeScreen {
  return {
    greeting: localGreeting(now),
    subtitle: null,
    urgent_todos: [],
    starters: [],
  };
}

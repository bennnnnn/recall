/** Sync first-paint home content — no network, no `@/lib/api` import
 * (keeps HomeProvider free of circular-module init races with Metro). */

import i18n from "@/lib/i18n";
import type { HomeScreen, HomeStarter } from "@/lib/api/types";

export function localGreeting(now: Date = new Date()): string {
  const hour = now.getHours();
  if (hour >= 5 && hour < 12) return i18n.t("chat.home.greeting_morning");
  if (hour >= 12 && hour < 17) return i18n.t("chat.home.greeting_afternoon");
  if (hour >= 17 && hour < 22) return i18n.t("chat.home.greeting_evening");
  return i18n.t("chat.home.greeting_night");
}

/** First paint / empty-account chips — no assumed day history. */
export function welcomeStarters(): HomeStarter[] {
  return [
    {
      text: i18n.t("chat.home.starter_help_think"),
      prompt: i18n.t("chat.home.starter_help_think_prompt"),
      kind: "general",
    },
    {
      text: i18n.t("chat.home.starter_what_can_you"),
      prompt: i18n.t("chat.home.starter_what_can_you_prompt"),
      kind: "general",
    },
  ];
}

/** Sync placeholder so post-login home never paints a bare spinner. */
export function instantHomePlaceholder(now: Date = new Date()): HomeScreen {
  return {
    greeting: localGreeting(now),
    subtitle: null,
    project_highlight: null,
    urgent_todos: [],
    starters: welcomeStarters(),
  };
}

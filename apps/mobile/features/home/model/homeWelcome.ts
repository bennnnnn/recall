/** The empty chat's greeting, built on the phone: no request, in the phone's language.
 *
 * The greeting came from `GET /home` on every start, return and token rotation; the
 * server's was English only and replaced the translated one (code-health audit NET-10). */

import i18n from "@/lib/i18n";
import { capitalisedName } from "@/lib/profile";

/**
 * What the home asks under the hello, in turn. One stays for `QUESTION_HOURS`, so the home
 * reads the same each time it is opened in that while, and changes through the day; six
 * slots a day over seven questions, so each day starts one further on.
 */
const QUESTIONS = [
  "working_on",
  "help_with",
  "on_your_mind",
  "where_start",
  "solving_today",
  "whats_next",
  "curious_about",
] as const;
const QUESTION_HOURS = 4;
const HOUR_MS = 60 * 60 * 1000;

/** The question for `now`'s slot, counted in local hours so a slot turns at 00:00, 04:00, … */
function questionAt(now: Date): (typeof QUESTIONS)[number] {
  const localHours = Math.floor((now.getTime() - now.getTimezoneOffset() * 60_000) / HOUR_MS);
  return QUESTIONS[Math.floor(localHours / QUESTION_HOURS) % QUESTIONS.length] ?? "help_with";
}

/**
 * The home's two lines: "Hi, Sam" (the first word of the account's name, when it has one)
 * and the slot's question, "What are you working on?".
 */
export function homeGreeting(
  name: string | null | undefined,
  now: Date = new Date(),
): { hello: string; question: string } {
  const word = name?.trim().split(/\s+/)[0];
  const first = word ? capitalisedName(word, i18n.language) : undefined;
  return {
    hello: first ? i18n.t("chat.home.hello_name", { name: first }) : i18n.t("chat.home.hello"),
    question: i18n.t(`chat.home.question_${questionAt(now)}`),
  };
}

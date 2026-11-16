/**
 * docs/fixtures/worked_words.json holds a worked layout's own words in each app language;
 * the API writes its headings in the reply's language from the same table
 * (`modules/chat/worked_language.py`, `test_worked_language.py`), and the phone reads them.
 */
import fixture from "../../../../../docs/fixtures/worked_words.json";

import { attachAnswerHeadingToFence } from "@/lib/markdown/attachAnswerHeading";
import { WORKED_WORDS } from "@/lib/markdown/workedWords";
import {
  isAnswerHeading,
  isGivenHeading,
  isRequiredHeading,
  isSolutionHeading,
  isWorkedReply,
  workoutHeading,
} from "@/lib/markdown/workoutSection";

describe("a worked layout's words", () => {
  it("are the fixture's, language by language", () => {
    expect(WORKED_WORDS).toEqual(fixture);
  });

  it.each(Object.entries(WORKED_WORDS))("are headings the phone lays out in %s", (_language, words) => {
    expect(isGivenHeading(words.given)).toBe(true);
    expect(isRequiredHeading(words.required)).toBe(true);
    expect(isSolutionHeading(words.solution)).toBe(true);
    expect(workoutHeading(words.substitution)).toBe(words.substitution);
    expect(workoutHeading(words.steps)).toBe(words.steps);
    expect(isAnswerHeading(words.answer)).toBe(true);
    expect(isAnswerHeading(`${words.answer} (b)`)).toBe(true);
    expect(
      isWorkedReply(`**${words.given}**  \n$v_0 = 0\\,\\mathrm{m/s}$\n\n**${words.required}**  \n$a$`),
    ).toBe(true);
  });

  it.each(Object.entries(WORKED_WORDS))("fold the %s Answer heading into its card, its part's letter kept", (_language, words) => {
    const card = "```answer\nverified: false\n5\\,\\mathrm{m/s^2}\n```";
    expect(attachAnswerHeadingToFence(`**${words.answer}**\n\n${card}`)).not.toContain(words.answer);
    const part = attachAnswerHeadingToFence(`**${words.answer} (b)**\n\n${card}`);
    expect(part).not.toContain(words.answer);
    expect(part).toContain("part: b");
  });
});

describe("a reply with one heading of another language's worked layout", () => {
  it.each([
    "**Datos**\n\nLa receta lleva harina, huevos y leche.",
    "**Dati**\n\nI risultati del sondaggio sono qui sotto.",
    "**Dados**\n\nOs números do relatório mudaram.",
  ])("is no worked reply: %s", (text) => {
    expect(isWorkedReply(text)).toBe(false);
  });

  it("is one with a second heading of the layout", () => {
    expect(isWorkedReply("**Datos**  \n$t = 5\\,\\mathrm{s}$\n\n**Respuesta**")).toBe(true);
  });

  it("is one when the heading is English, as before", () => {
    expect(isWorkedReply("**Given**  \n$t = 5$")).toBe(true);
    expect(isWorkedReply("**Required:** the force $F$")).toBe(true);
  });
});

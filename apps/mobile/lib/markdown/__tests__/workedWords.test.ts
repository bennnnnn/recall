/**
 * docs/fixtures/worked_words.json holds a worked layout's own words in each app language;
 * the API writes its headings in the reply's language from the same table
 * (`modules/chat/worked_language.py`, `test_worked_language.py`), and the phone reads them.
 */
import fixture from "../../../../../docs/fixtures/worked_words.json";

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
    expect(isWorkedReply(`**${words.given}**  \n$v_0 = 0\\,\\mathrm{m/s}$`)).toBe(true);
  });
});

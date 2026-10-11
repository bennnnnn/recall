/**
 * The phone reads composer image intent exactly the way the server does.
 * docs/fixtures/image_intent_cases.json is shared with the API test
 * (app/tests/modules/images/test_intent_contract.py), so a rule changed on one
 * side alone fails a suite.
 */
import {
  extractImageGenPrompt,
  extractImageGenPromptFromThread,
  extractImageRevisionPrompt,
  imageGenRevisionContext,
} from "@/features/images/model/imageGenIntent";
import { extractImageLookupQuery } from "@/features/images/model/imageLookupIntent";

import fixture from "../../../../../../docs/fixtures/image_intent_cases.json";

type Phrase = { text: string; generate: string | null; revise: string | null; lookup: string | null };
type Thread = { text: string; priors: string[]; generate: string | null };
type RevisionContext = {
  messages: { role: string; content: string; model?: string }[];
  last_assistant_is_image_only: boolean;
  previous_subject: string | null;
};
type Contract = {
  revise_previous_subject: string;
  phrases: Phrase[];
  threads: Thread[];
  revision_contexts: RevisionContext[];
};

const contract: Contract = fixture;
const label = (text: string) => JSON.stringify(text).slice(0, 60);

describe("image intent contract", () => {
  it.each(contract.phrases.map((c) => [label(c.text), c] as const))("%s", (_label, c) => {
    expect(extractImageGenPrompt(c.text)).toBe(c.generate);
    expect(extractImageLookupQuery(c.text)).toBe(c.lookup);
    expect(
      extractImageRevisionPrompt(c.text, {
        lastAssistantIsImageOnly: true,
        previousSubject: contract.revise_previous_subject,
      }),
    ).toBe(c.revise);
  });

  it.each(contract.threads.map((c) => [label(c.text), c] as const))("thread %s", (_label, c) => {
    const messages = c.priors.map((content, i) => ({ id: `u${i}`, role: "user", content }));
    expect(extractImageGenPromptFromThread(c.text, messages)).toBe(c.generate);
  });

  it.each(contract.revision_contexts.map((c, i) => [i, c] as const))("revision context %d", (_i, c) => {
    const rows = c.messages.map((m, i) => ({ id: `m${i}`, ...m }));
    const context = imageGenRevisionContext(rows);
    expect([context.lastAssistantIsImageOnly, context.previousSubject]).toEqual([
      c.last_assistant_is_image_only,
      c.previous_subject,
    ]);
  });
});

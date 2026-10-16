/**
 * docs/fixtures/presentation_cases.json is shared with the API test
 * (app/tests/modules/chat/test_presentation.py): the server presents a reply
 * before it is saved, the phone presents the text still streaming and rows
 * saved before the server did. Both must give every input the same output.
 */
import { preprocessMarkdown } from "@/lib/markdown/preprocess";
import { preprocessMarkdownForStream } from "@/lib/markdown/preprocessStream";
import { presentAssistantMarkdown, presentStreamTail } from "@/lib/markdown/presentation";

import fixture from "../../../../docs/fixtures/presentation_cases.json";

type PresentationCase = {
  id: string;
  area: string;
  input: string;
  expected: string;
  note?: string;
};

const CASES: PresentationCase[] = fixture.cases;
const byId = (id: string): PresentationCase => {
  const found = CASES.find((c) => c.id === id);
  if (!found) throw new Error(`no presentation case ${id}`);
  return found;
};

describe("presentation corpus", () => {
  it.each(CASES.map((c) => [c.id, c] as const))("%s presents as the server does", (_id, c) => {
    expect(presentAssistantMarkdown(c.input)).toBe(c.expected);
  });

  it.each(CASES.map((c) => [c.id, c] as const))("%s presents to itself once presented", (_id, c) => {
    expect(presentAssistantMarkdown(c.expected)).toBe(c.expected);
  });
});

describe("streaming presentation", () => {
  it("streams closed prose and calculation rows the way they settle", () => {
    const sources = [
      byId("bold-glued-train").input,
      byId("bold-glued-cyclist").input,
      byId("bold-punctuation-stays-tight").input,
      `${byId("equals-chain").input}\n`,
      byId("paren-chain-across-lines").input,
    ];
    for (const source of sources) {
      expect(preprocessMarkdownForStream(source, null).prepared).toBe(preprocessMarkdown(source));
    }
    const partial = preprocessMarkdownForStream("at**40", null).prepared;
    expect(partial).toBe("at**40");
    expect(partial).toBe(presentAssistantMarkdown("at**40"));
  });

  it("wraps a bare fraction on the streaming tail and leaves an open fence alone", () => {
    const wrapped = presentStreamTail(String.raw`half is \frac{1}{2}`);
    expect(wrapped).toContain(String.raw`$\frac{1}{2}$`);
    expect(wrapped).not.toMatch(/(?:^|[^$])\\frac/);
    const openFence = presentStreamTail(String.raw`see` + "\n```\n\\frac{1}{2}\n");
    expect(openFence.startsWith("see")).toBe(true);
    expect(openFence).toContain("```\n\\frac{1}{2}\n");
    expect(openFence).not.toContain("$\\frac");
    expect(preprocessMarkdownForStream(String.raw`half is \frac{1}{2}`, null).prepared).toBe(wrapped);
    const openDollar = presentStreamTail(String.raw`$\frac{1}{2}`);
    expect(openDollar).toBe(String.raw`$\frac{1}{2}`);
    expect(openDollar).not.toContain("$$");
    expect(presentStreamTail(String.raw`see \(\frac{1}`)).toBe(String.raw`see \(\frac{1}`);
  });
});

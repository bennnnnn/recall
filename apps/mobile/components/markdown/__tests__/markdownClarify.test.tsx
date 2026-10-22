import { fireEvent, render } from "@testing-library/react-native";

import { MarkdownContent } from "@/components/MarkdownContent";
import { ClarifyActionsProvider, ClarifyMessageScope } from "@/components/rich/clarifyContext";
import { markdownToCopyText } from "@/lib/markdown/plain";

jest.mock("@/components/LinkPreviewCard", () => {
  const { Text } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    LinkPreviewCard: ({ url }: { url: string }) => <Text>{url}</Text>,
  };
});

const CARD =
  "```clarify\n" +
  '{"when":"first","questions":[{"id":"level","label":"Studied it before",' +
  '"question":"Have you studied integrals before?","options":["No, never","A little",' +
  '"Yes, I\'m revising"],"multi":false},{"id":"goal","label":"What it\'s for",' +
  '"question":"What do you need it for?","options":["An exam","A class","Curiosity"],' +
  '"multi":false}]}\n```';

/** A reply that asks first: one sentence, then the card (docs/clarify.md). */
const REPLY = `Before I explain, two quick questions so I can pitch it right:\n\n${CARD}`;

function visibleText(view: ReturnType<typeof render> extends Promise<infer R> ? R : never): string {
  const parts: string[] = [];
  const walk = (node: unknown) => {
    if (typeof node === "string") {
      parts.push(node);
      return;
    }
    if (!node || typeof node !== "object") return;
    if (Array.isArray(node)) {
      node.forEach(walk);
      return;
    }
    walk((node as { children?: unknown }).children);
  };
  walk(view.toJSON());
  return parts.join("");
}

describe("a reply that asks with a clarify card", () => {
  it("never shows the card's JSON while it streams", async () => {
    for (let end = 1; end <= REPLY.length; end += 7) {
      const view = await render(<MarkdownContent content={REPLY.slice(0, end)} streaming />);
      const shown = visibleText(view);
      expect({ end, shown }).toEqual({ end, shown: expect.not.stringContaining('"questions"') });
      expect({ end, shown }).toEqual({ end, shown: expect.not.stringContaining('"label"') });
      await view.unmount();
    }
  });

  it("draws the card under the sentence once the reply is complete, and sends the picks", async () => {
    const send = jest.fn();
    const view = await render(
      <ClarifyActionsProvider send={send} busy={false}>
        <ClarifyMessageScope latest nextUserText={null}>
          <MarkdownContent content={REPLY} />
        </ClarifyMessageScope>
      </ClarifyActionsProvider>,
    );
    const shown = visibleText(view);
    expect(shown).toContain("Before I explain, two quick questions");
    expect(shown).toContain("Have you studied integrals before?");
    expect(shown).not.toContain('"questions"');
    await fireEvent.press(view.getByText("A little"));
    await fireEvent.press(view.getByText("An exam"));
    await fireEvent.press(view.getByText("Submit"));
    expect(send).toHaveBeenCalledWith("Studied it before: A little\nWhat it's for: An exam");
  });

  it("copies the questions and their choices, not the JSON", () => {
    const copied = markdownToCopyText(REPLY);
    expect(copied).toContain("Have you studied integrals before? (No, never / A little / Yes, I'm revising)");
    expect(copied).not.toContain('"questions"');
  });
});

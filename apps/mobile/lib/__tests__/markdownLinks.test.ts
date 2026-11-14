import { markdownItInstance } from "@/lib/markdown/parser";

/** The hrefs the parser links in one line of text. */
function linkedHrefs(text: string): string[] {
  return markdownItInstance
    .parseInline(text, {})
    .flatMap((token) => token.children ?? [])
    .filter((child) => child.type === "link_open")
    .map((child) => String(child.attrGet("href")));
}

describe("links the parser finds in plain text", () => {
  // markdown-it 15's linkify-it 6 stopped linking a bare domain unless asked; the app
  // has always shown one as a link.
  it.each([
    ["Try example.com today", "http://example.com"],
    ["See www.example.org for more", "http://www.example.org"],
    ["Docs at docs.python.org/3/library", "http://docs.python.org/3/library"],
    ["Open https://example.com/a?b=1 now", "https://example.com/a?b=1"],
    ["Write to bob@example.com", "mailto:bob@example.com"],
  ])("links %s", (text, href) => {
    expect(linkedHrefs(text)).toEqual([href]);
  });

  it.each(["Price is 3.5 today", "Version 2.1.0 shipped", "No link here"])(
    "links nothing in %s",
    (text) => {
      expect(linkedHrefs(text)).toEqual([]);
    },
  );
});

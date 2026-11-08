/**
 * Lists print as the chat shows them. A reply that put each item's paragraph under its bold
 * name ("1. **Read widely**\" then the paragraph) printed every item as "1." with a stray
 * backslash, since each paragraph ended the list (exported PDF, 2026-11-07).
 */
import { markdownToStructuredPrintHtml } from "@/features/chat/model/printDocument";

jest.mock("@/lib/i18n", () => ({
  __esModule: true,
  default: { t: (key: string) => key },
}));

async function body(markdown: string): Promise<string> {
  const html = await markdownToStructuredPrintHtml("Chat", markdown);
  return html.slice(html.indexOf("<h1>"), html.indexOf("</body>")).replace(/\s*\n\s*/g, "");
}

it("keeps an item's paragraph in the item and the list numbered", async () => {
  const html = await body(
    [
      "Here are the ways:",
      "",
      "1. **Read widely**\\",
      "   Don't stick to one genre.",
      "",
      "2. **Learn how to learn**\\",
      "   Study with spaced repetition.",
      "",
      "Start with one.",
    ].join("\n"),
  );
  expect(html).toContain(
    "<ol><li><strong>Read widely</strong><br>Don't stick to one genre.</li>" +
      "<li><strong>Learn how to learn</strong><br>Study with spaced repetition.</li></ol>",
  );
  expect(html).not.toContain("\\");
  expect(html).toContain("<p>Start with one.</p>");
});

it("starts an ordered list at its first number", async () => {
  expect(await body("3. Third\n4. Fourth")).toContain('<ol start="3"><li>Third</li><li>Fourth</li></ol>');
});

it("nests an indented list inside its item", async () => {
  const html = await body("- Fruit\n  - Apple\n  - Pear\n- Bread");
  expect(html).toContain("<ul><li>Fruit<ul><li>Apple</li><li>Pear</li></ul></li><li>Bread</li></ul>");
});

it("keeps a two-paragraph item's paragraphs whole", async () => {
  const html = await body("1. First\n\n   More about the first.\n2. Second");
  expect(html).toContain("<ol><li><p>First</p><p>More about the first.</p></li><li>Second</li></ol>");
});

it("joins a lazy continuation line to the item, and ends the list at a heading", async () => {
  const html = await body("- one\ncontinued\n## Next");
  expect(html).toContain("<ul><li>one continued</li></ul>");
  expect(html).toContain("<h3>Next</h3>");
});

it("reads a tight bullet list and a numbered list that follows as two lists", async () => {
  const html = await body("- a\n- b\n\n1. c\n2. d");
  expect(html).toContain("<ul><li>a</li><li>b</li></ul><ol><li>c</li><li>d</li></ol>");
});

it("prints a thematic break as a rule, not as nested lists", async () => {
  for (const rule of ["* * *", "***", "---", "- - -"]) {
    const html = await body(`Before\n\n${rule}\n\nAfter`);
    expect(html).toContain("<p>Before</p><hr><p>After</p>");
    expect(html).not.toContain("<ul>");
  }
});

it("prints a list nested past any sense as text, without overflowing", async () => {
  const html = await body(`${"- ".repeat(3000)}deep`);
  expect(html).toContain("deep");
  expect(html.split("<ul>").length - 1).toBeLessThanOrEqual(13);
});

import { markdownToStructuredPrintHtml } from "@/lib/printDocument";

jest.mock("@/lib/vendorAssets", () => ({
  readVendorLibrary: jest.fn(async () => ""),
}));

const body = async (markdown: string) => {
  const html = await markdownToStructuredPrintHtml("T", markdown);
  return html.slice(html.indexOf("<body>"));
};

describe("PDF print document", () => {
  it("typesets an answer card instead of printing its LaTeX", async () => {
    const html = await body("```answer\nverified: true\nx = \\frac{1}{2}\n```");
    expect(html).toContain('class="answer"');
    expect(html).toContain("katex");
    expect(html).not.toContain("verified: true");
    expect(html).not.toContain("<pre>");
  });

  it("prints a chemistry or sentence answer as text", async () => {
    expect(await body("```answer\nnotation: chemistry\nH₂O\n```")).toContain("<p>H₂O</p>");
    const sentence = await body("```answer\nIt lands after $t = 2$ s.\n```");
    expect(sentence).toContain("It lands after");
    expect(sentence).toContain("katex");
  });

  it("keeps underscores inside words and code", async () => {
    const html = await body("Use `proposal_id` and due_at, but _this_ is emphasis.");
    expect(html).toContain("<code>proposal_id</code>");
    expect(html).toContain("due_at");
    expect(html).toContain("<em>this</em>");
    expect(html).not.toContain("<em>id");
  });

  it("keeps a code span's asterisks and an emphasis star", async () => {
    const html = await body("Run `a * b * c` then *done*.");
    expect(html).toContain("<code>a * b * c</code>");
    expect(html).toContain("<em>done</em>");
  });

  it("wraps long code lines and borders tables", async () => {
    const html = await markdownToStructuredPrintHtml("T", "| a | b |\n|---|---|\n| 1 | 2 |");
    expect(html).toContain("white-space: pre-wrap");
    expect(html).toMatch(/th, td \{ border: 1px solid/);
    expect(html).toContain("<table>");
  });
});

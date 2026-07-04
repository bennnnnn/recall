import { markdownToPlainText, markdownToPrintHtml } from "@/lib/markdownPlain";

describe("markdownPlain", () => {
  it("strips fences and markdown emphasis", () => {
    const plain = markdownToPlainText("# Title\n\n**Bold** and `code`\n\n```json\n{}\n```");
    expect(plain).toContain("Title");
    expect(plain).toContain("Bold");
    expect(plain).not.toContain("```");
  });

  it("builds print html with escaped title", () => {
    const html = markdownToPrintHtml('Report <script>', "Hello");
    expect(html).toContain("Report &lt;script&gt;");
    expect(html).toContain("Hello");
  });
});

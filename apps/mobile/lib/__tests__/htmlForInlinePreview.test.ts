import { htmlForInlinePreview } from "@/lib/htmlForInlinePreview";
import { stripScripts } from "@/lib/previewSandbox";

describe("htmlForInlinePreview + stripScripts (Expo Go static fallback)", () => {
  it("strips <script> blocks before the static renderer sees them", () => {
    // The Expo Go static fallback path runs stripScripts(html) before
    // htmlForInlinePreview so a model-emitted <script> body is not dumped
    // as visible text and inline event handlers are removed.
    const html =
      '<!DOCTYPE html><html><head><title>x</title></head><body>' +
      "<script>alert('hi')</script><p>hello</p>" +
      '<div onclick="alert(2)">x</div>' +
      "</body></html>";
    const out = htmlForInlinePreview(stripScripts(html));
    expect(out.toLowerCase()).not.toContain("<script");
    expect(out.toLowerCase()).not.toContain("alert");
    expect(out.toLowerCase()).not.toContain("onclick");
    expect(out).toContain("hello");
  });

  it("strips javascript: URLs from href before the static renderer sees them", () => {
    const html =
      '<body><a href="javascript:alert(1)">click</a><a href="https://example.com">safe</a></body>';
    const out = htmlForInlinePreview(stripScripts(html));
    expect(out.toLowerCase()).not.toContain("javascript:");
    expect(out).toContain("https://example.com");
  });
});

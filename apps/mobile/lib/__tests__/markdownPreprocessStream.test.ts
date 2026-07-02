import { preprocessMarkdown } from "@/lib/markdownPreprocess";
import {
  findStableMarkdownPrefixLen,
  preprocessMarkdownForStream,
} from "@/lib/markdownPreprocessStream";

describe("markdownPreprocessStream", () => {
  it("treats a trailing partial line as unstable", () => {
    expect(findStableMarkdownPrefixLen("Hello wor")).toBe(0);
    expect(findStableMarkdownPrefixLen("Line one\nLine two")).toBe("Line one\n".length);
  });

  it("excludes an unclosed code fence from the stable prefix", () => {
    const input = "Intro\n\n```python\nprint('hi')\n";
    expect(findStableMarkdownPrefixLen(input)).toBe("Intro\n\n".length);
  });

  it("includes a closed code fence in the stable prefix", () => {
    const input = "Intro\n\n```python\nprint('hi')\n```\n\nDone.\n";
    expect(findStableMarkdownPrefixLen(input)).toBe(input.length);
  });

  it("reuses cached stable output and leaves the unstable tail raw", () => {
    const stable = "The area is $$\\pi r^2$$ for a circle.\n\n";
    const growing = `${stable}More text in pro`;
    const first = preprocessMarkdownForStream(stable, null);
    const second = preprocessMarkdownForStream(growing, first.cache);

    expect(first.prepared).toContain("```math");
    expect(second.prepared.startsWith(first.prepared)).toBe(true);
    expect(second.prepared.endsWith("More text in pro")).toBe(true);
    expect(second.cache.rawStableLen).toBe(stable.length);
  });

  it("matches full preprocess once the stream completes", () => {
    const content = "The area is $$\\pi r^2$$ for a circle.\n\nTail line.\n";
    const streamed = preprocessMarkdownForStream(content, null).prepared;
    expect(streamed).toBe(preprocessMarkdown(content));
  });
});

import {
  faviconUrl,
  hostnameFromUrl,
  parseSearchSources,
  stripSearchSourcesFromContent,
} from "@/lib/searchSources";

describe("searchSources", () => {
  it("parses sources fence", () => {
    const content = `Here is the answer.

\`\`\`sources
[{"title":"AP News","url":"https://apnews.com/a","snippet":"Story text."}]
\`\`\``;
    expect(parseSearchSources(content)).toEqual([
      {
        title: "AP News",
        url: "https://apnews.com/a",
        snippet: "Story text.",
      },
    ]);
    expect(stripSearchSourcesFromContent(content)).toBe("Here is the answer.");
  });

  it("returns empty when fence missing", () => {
    expect(parseSearchSources("hello")).toEqual([]);
  });

  it("parses trailing bare JSON source arrays from the model", () => {
    const content = `Here is the answer.

[{"title":"AP News","url":"https://apnews.com/a","snippet":"Story text."}]`;
    expect(parseSearchSources(content)).toEqual([
      {
        title: "AP News",
        url: "https://apnews.com/a",
        snippet: "Story text.",
      },
    ]);
    expect(stripSearchSourcesFromContent(content)).toBe("Here is the answer.");
  });

  it("strips bare code fences and a sources label around JSON", () => {
    const content = `It's afternoon there.

**sources**
\`\`\`
[{"title":"Current Time in Washington, D.C.","url":"http://www.timeandzone.com/dc"}]
\`\`\``;
    expect(parseSearchSources(content)).toEqual([
      {
        title: "Current Time in Washington, D.C.",
        url: "http://www.timeandzone.com/dc",
      },
    ]);
    expect(stripSearchSourcesFromContent(content)).toBe("It's afternoon there.");
  });

  it("does not hang when content starts with an unparseable '[' (e.g. an image marker)", () => {
    // Regression: lastIndexOf("[", -1) clamps to 0 instead of returning -1,
    // so the old loop re-found the same leading "[" forever once it reached
    // index 0 without finding valid trailing JSON. Every generated-image
    // reply is exactly this shape ("[Image: /attachments/<id>/file]"), so
    // this previously froze the JS thread on every image generation.
    const content = "[Image: /attachments/11111111-1111-1111-1111-111111111111/file]";
    expect(parseSearchSources(content)).toEqual([]);
    expect(stripSearchSourcesFromContent(content)).toBe(content);
  }, 2000);

  it("does not hang on other unparseable leading-bracket content", () => {
    expect(parseSearchSources("[not json at all")).toEqual([]);
    expect(parseSearchSources("[[[[[")).toEqual([]);
  }, 2000);

  it("extracts hostname", () => {
    expect(hostnameFromUrl("https://www.bbc.com/news")).toBe("bbc.com");
  });

  it("builds favicon url from host", () => {
    expect(faviconUrl("https://www.bbc.com/news")).toContain("bbc.com");
  });
});

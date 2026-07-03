import {
  faviconUrl,
  hostnameFromUrl,
  parseSearchSources,
  stripSearchSourcesFence,
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
    expect(stripSearchSourcesFence(content)).toBe("Here is the answer.");
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

  it("extracts hostname", () => {
    expect(hostnameFromUrl("https://www.bbc.com/news")).toBe("bbc.com");
  });

  it("builds favicon url from host", () => {
    expect(faviconUrl("https://www.bbc.com/news")).toContain("bbc.com");
  });
});

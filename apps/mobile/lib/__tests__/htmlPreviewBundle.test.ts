import {
  bundleHtmlPreview,
  collectPreviewFiles,
  fenceLangFromInfo,
  previewHasSiblingAssets,
  sanitizePreviewFilename,
} from "@/lib/htmlPreviewBundle";

describe("fenceLangFromInfo", () => {
  it("reads the language and ignores a filename", () => {
    expect(fenceLangFromInfo("html index.html")).toBe("html");
    expect(fenceLangFromInfo("css styles.css")).toBe("css");
    expect(fenceLangFromInfo("javascript app.js")).toBe("javascript");
  });
});

describe("sanitizePreviewFilename", () => {
  it("accepts a basename with the right extension", () => {
    expect(sanitizePreviewFilename("styles.css", "css")).toBe("styles.css");
    expect(sanitizePreviewFilename("app.js", "js")).toBe("app.js");
  });

  it("rejects folders, traversal, and the wrong extension", () => {
    expect(sanitizePreviewFilename("../x.css", "css")).toBe("x.css");
    expect(sanitizePreviewFilename("foo/bar.css", "css")).toBe("bar.css");
    expect(sanitizePreviewFilename("styles.css", "js")).toBeNull();
    expect(sanitizePreviewFilename("nope", "css")).toBeNull();
    expect(sanitizePreviewFilename("a b.css", "css")).toBeNull();
  });
});

describe("collectPreviewFiles", () => {
  it("collects named html/css/js siblings and skips other langs", () => {
    const md = [
      "Here is a page:",
      "",
      "```html index.html",
      "<h1>Hi</h1>",
      "```",
      "",
      "```css styles.css",
      "h1 { color: red; }",
      "```",
      "",
      "```javascript app.js",
      "console.log(1)",
      "```",
      "",
      "```python",
      "print(1)",
      "```",
    ].join("\n");
    const files = collectPreviewFiles(md);
    expect(files.map((f) => f.name)).toEqual(["index.html", "styles.css", "app.js"]);
    expect(previewHasSiblingAssets(files)).toBe(true);
  });

  it("assigns default names when the fence has no filename", () => {
    const md = "```html\n<p>a</p>\n```\n\n```css\nbody{}\n```\n";
    const files = collectPreviewFiles(md);
    expect(files.map((f) => f.name)).toEqual(["index.html", "styles.css"]);
  });
});

describe("bundleHtmlPreview", () => {
  it("returns the entry unchanged when there are no css/js siblings", () => {
    const html = "<p>solo</p>";
    expect(bundleHtmlPreview(html, [{ kind: "html", name: "index.html", content: html }])).toBe(
      html,
    );
  });

  it("inlines a linked stylesheet and script", () => {
    const html =
      '<html><head><link rel="stylesheet" href="styles.css"></head>' +
      '<body><script src="app.js"></script></body></html>';
    const out = bundleHtmlPreview(html, [
      { kind: "html", name: "index.html", content: html },
      { kind: "css", name: "styles.css", content: "h1{color:red}" },
      { kind: "js", name: "app.js", content: "window.ready=1" },
    ]);
    expect(out).toContain("<style>");
    expect(out).toContain("h1{color:red}");
    expect(out).toContain("window.ready=1");
    expect(out).not.toContain("href=\"styles.css\"");
    expect(out).not.toContain("src=\"app.js\"");
  });

  it("appends unlinked css/js so the model can omit link tags", () => {
    const html = "<html><head></head><body><h1>Hi</h1></body></html>";
    const out = bundleHtmlPreview(html, [
      { kind: "html", name: "index.html", content: html },
      { kind: "css", name: "styles.css", content: "h1{color:blue}" },
      { kind: "js", name: "app.js", content: "window.n=2" },
    ]);
    expect(out).toContain("h1{color:blue}");
    expect(out).toContain("window.n=2");
    expect(out.indexOf("h1{color:blue}")).toBeLessThan(out.indexOf("</head>"));
    expect(out.indexOf("window.n=2")).toBeLessThan(out.indexOf("</body>"));
  });

  it("does not inline a path that is not a sibling file", () => {
    const html = '<link rel="stylesheet" href="https://cdn.example/x.css">';
    const out = bundleHtmlPreview(html, [
      { kind: "html", name: "index.html", content: html },
      { kind: "css", name: "styles.css", content: "body{}" },
    ]);
    expect(out).toContain("https://cdn.example/x.css");
    expect(out).toContain("body{}");
  });
});

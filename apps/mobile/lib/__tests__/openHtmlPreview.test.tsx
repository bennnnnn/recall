import { darkTheme, lightTheme } from "@/lib/theme";

import { wrapFullDocument } from "@/lib/openHtmlPreview";

// openHtmlPreview pulls in expo-file-system (Share/export path) and
// expo-web-browser, whose native modules aren't linked in this jest env.
jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  writeAsStringAsync: jest.fn(),
  EncodingType: { UTF8: "utf8" },
}));
jest.mock("expo-web-browser", () => ({
  openBrowserAsync: jest.fn(),
}));

describe("wrapFullDocument", () => {
  it("passes through a document that already has its own shell", () => {
    const doc = `<!DOCTYPE html><html><head></head><body><p>x</p></body></html>`;
    expect(wrapFullDocument(doc)).toBe(doc);
    expect(wrapFullDocument(doc, darkTheme)).toBe(doc);
  });

  it("defaults to a light canvas when no theme is given (system-browser export path)", () => {
    const out = wrapFullDocument("<p>hi</p>");
    expect(out).toContain("color: #111827");
    expect(out).toContain("background: #FFFFFF");
  });

  it("DS-01: threads dark-mode tokens so the in-app Run tab is not a white sheet", () => {
    const out = wrapFullDocument("<p>hi</p>", darkTheme);
    expect(out).toContain(`color: ${darkTheme.text}`);
    expect(out).toContain(`background: ${darkTheme.bg}`);
    expect(out).toContain(`border: 1px solid ${darkTheme.border}`);
    expect(out).toContain(`th { background: ${darkTheme.surface}`);
    // The light-only Tailwind palette must not leak into a dark preview.
    expect(out).not.toContain("#111827");
    expect(out).not.toContain("#E5E7EB");
    expect(out).not.toContain("#F1F5F9");
  });

  it("threads light-mode tokens when the light theme is active", () => {
    const out = wrapFullDocument("<p>hi</p>", lightTheme);
    expect(out).toContain(`color: ${lightTheme.text}`);
    expect(out).toContain(`background: ${lightTheme.bg}`);
  });

  it("uses the shared code font, not a one-off 'SF Mono'", () => {
    expect(wrapFullDocument("<p>hi</p>", darkTheme)).not.toContain("'SF Mono'");
  });
});

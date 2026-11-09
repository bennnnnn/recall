import { writeAsStringAsync } from "expo-file-system/legacy";
import { openBrowserAsync } from "expo-web-browser";
import { Linking, Share } from "react-native";

import { darkTheme, lightTheme } from "@/lib/theme";

import { openHtmlInBrowser, shareHtmlPreview, wrapFullDocument } from "@/lib/preview/openHtmlPreview";
import { HTML_EXPORT_CSP } from "@/lib/preview/previewSandbox";
import { shareLocalFile } from "@/lib/share/file";

// openHtmlPreview pulls in expo-file-system (Share/export path) and
// expo-web-browser, whose native modules aren't linked in this jest env.
jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  writeAsStringAsync: jest.fn(),
  makeDirectoryAsync: jest.fn(async () => undefined),
  readDirectoryAsync: jest.fn(async () => []),
  deleteAsync: jest.fn(async () => undefined),
  EncodingType: { UTF8: "utf8" },
}));
jest.mock("expo-web-browser", () => ({
  openBrowserAsync: jest.fn(),
}));
// How a file reaches the sheet on each platform is shareFile.test.ts's.
jest.mock("@/lib/share/file", () => ({ shareLocalFile: jest.fn(async () => undefined) }));

beforeEach(() => {
  jest.restoreAllMocks();
  jest.mocked(shareLocalFile).mockReset().mockResolvedValue(undefined);
  jest.mocked(openBrowserAsync).mockReset();
  jest.mocked(writeAsStringAsync).mockReset();
});

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

const DATA_URL_PREFIX = "data:text/html;charset=utf-8,";
const CSP_META = `<meta http-equiv="Content-Security-Policy" content="${HTML_EXPORT_CSP}">`;
/** What the exported document starts with: its charset, then its CSP. */
const EXPORT_HEAD = `<!DOCTYPE html><meta charset="utf-8">${CSP_META}`;
const UTF8_BOM = "\uFEFF";

/** The document "Open in browser" hands the system browser as a data: URL. */
async function openedDocument(html: string): Promise<string> {
  const open = jest.spyOn(Linking, "openURL").mockResolvedValue(undefined);
  open.mockClear();
  await expect(openHtmlInBrowser(html, "HTML preview")).resolves.toBeUndefined();
  const url = String(open.mock.calls[0]?.[0]);
  expect(url.startsWith(DATA_URL_PREFIX)).toBe(true);
  return decodeURIComponent(url.slice(DATA_URL_PREFIX.length));
}

/** The file Share writes and hands the share sheet, after its byte-order mark. */
async function sharedDocument(html: string): Promise<string> {
  jest.mocked(writeAsStringAsync).mockClear();
  jest.mocked(shareLocalFile).mockClear();
  await expect(shareHtmlPreview(html, "HTML preview")).resolves.toBeUndefined();
  const [uri, file] = jest.mocked(writeAsStringAsync).mock.calls[0] ?? [];
  expect(shareLocalFile).toHaveBeenCalledWith(uri, { title: "HTML preview", mimeType: "text/html" });
  expect(String(file).startsWith(UTF8_BOM)).toBe(true);
  return String(file).slice(UTF8_BOM.length);
}

/**
 * The charset and the CSP are the document's first elements: the parser puts
 * them in the head it opens, before anything else in the document can run or load.
 */
function expectCspInHead(doc: string): void {
  expect(doc.startsWith(EXPORT_HEAD)).toBe(true);
  expect(doc.split("Content-Security-Policy")).toHaveLength(2);
}

describe("exported HTML (Open in browser, Share)", () => {
  it.each([
    ["a fragment", "<p>hi</p>"],
    ["a full document", "<!DOCTYPE html><html><head><title>t</title></head><body>hi</body></html>"],
    ["body content before its <head>", "<!DOCTYPE html><html>hi<head><title>t</title></head><body></body></html>"],
  ])("carries the export CSP as the first element of its head: %s", async (_what, html) => {
    expectCspInHead(await openedDocument(html));
    expectCspInHead(await sharedDocument(html));
  });

  it("carries the CSP on the file path a large page takes, and when data: URLs are refused", async () => {
    jest.mocked(writeAsStringAsync).mockClear();
    jest.spyOn(Linking, "openURL").mockResolvedValue(undefined);
    await openHtmlInBrowser(`<p>${"x".repeat(130_000)}</p>`, "HTML preview");
    const file = String(jest.mocked(writeAsStringAsync).mock.calls[0]?.[1]);
    expect(file.startsWith(UTF8_BOM)).toBe(true);
    expectCspInHead(file.slice(UTF8_BOM.length));

    jest.spyOn(Linking, "openURL").mockRejectedValue(new Error("no handler"));
    jest.mocked(openBrowserAsync).mockClear();
    await openHtmlInBrowser("<p>hi</p>", "HTML preview");
    const url = String(jest.mocked(openBrowserAsync).mock.calls[0]?.[0]);
    expectCspInHead(decodeURIComponent(url.slice(DATA_URL_PREFIX.length)));
  });


  // Each got through stripScripts into the exported document on main.
  it.each([
    ["&#106;", '<a href="&#106;avascript:alert(1)">x</a>', /href|avascript/i],
    ["&#x6A;", '<a href="&#x6A;avascript:alert(1)">x</a>', /href|avascript/i],
    ["&colon;", '<a href="javascript&colon;alert(1)">x</a>', /href|javascript/i],
    ["&#x09;", '<a href="jav&#x09;ascript:alert(1)">x</a>', /href|ascript/i],
    ["&Tab;", '<a href="jav&Tab;ascript:alert(1)">x</a>', /href|ascript/i],
    ["svg xlink:href", '<svg><a xlink:href="javascript:alert(1)"><text y="20">x</text></a></svg>', /href|javascript/i],
    ["svg use data:", '<svg><use xlink:href="data:image/svg+xml,%3Csvg%20id=%22x%22/%3E#x"/></svg>', /href|data:/i],
    ["mixed case", '<A HrEf="JaVaScRiPt:alert(1)">x</A>', /href|javascript/i],
    ["control characters", '<a href="\u0001 java\nscript:alert(1)">x</a>', /href|script:/i],
    ["handler without a space", '<img src="x"onerror="alert(1)">', /onerror/i],
    ["assembled <script>", '<scr onx="y"ipt>alert(1)</script>', /<script/i],
  ])("neutralises %s in the exported document", async (_name, html, gone) => {
    for (const doc of [await openedDocument(html), await sharedDocument(html)]) {
      expectCspInHead(doc);
      expect(doc.slice(EXPORT_HEAD.length)).not.toMatch(gone);
    }
  });

  // A file has no transport charset, so a browser reads the page's own <meta
  // charset>. ISO-2022-JP drops "ESC ( B", which joins "http-equ" and "iv" into a
  // pragma after the disarming already ran on the JS string. The byte-order mark
  // (and the utf-8 meta ahead of the page's) keep the file UTF-8 whatever it says.
  it("is read as UTF-8 whatever charset the page declares", async () => {
    const html =
      '<!DOCTYPE html><html><head><meta charset="iso-2022-jp">' +
      '<meta http-equ\u001b(Biv=refresh content="0;url=https://evil.example/"></head><body>x</body></html>';
    const doc = await sharedDocument(html);
    expect(doc.startsWith(EXPORT_HEAD)).toBe(true);
    expect(doc.indexOf('<meta charset="utf-8">')).toBeLessThan(doc.indexOf('charset="iso-2022-jp"'));
    expect(new TextDecoder("utf-8").decode(new TextEncoder().encode(doc))).not.toContain("http-equiv=refresh");
  });
});

// Share handed Android the cache file's path as text ("file:///data/…/recall-preview-1.html")
// in place of the page, under an English title, and a failure was dropped.
describe("Share and Open in browser hand over the file", () => {
  const share = () => jest.spyOn(Share, "share");

  // It went out as "recall-preview-1731…html" at the cache's root, which only sign-out cleared.
  it("shares the page itself under a name a person reads, from a share folder swept like the rest", async () => {
    await sharedDocument("<p>hi</p>");
    const [uri] = jest.mocked(shareLocalFile).mock.calls[0] ?? [];
    expect(String(uri)).toMatch(/^file:\/\/\/cache\/recall-share-\d+-\d+\/HTML%20preview\.html$/);
    expect(share()).not.toHaveBeenCalled();
  });

  it("shares the file when no browser takes the page (iOS opens neither data: nor file: URLs)", async () => {
    jest.spyOn(Linking, "openURL").mockRejectedValue(new Error("Unable to open URL"));
    jest.mocked(openBrowserAsync).mockRejectedValue(new Error("Only http and https URLs are supported"));
    await expect(openHtmlInBrowser("<p>hi</p>", "HTML preview")).resolves.toBeUndefined();
    const [uri] = jest.mocked(writeAsStringAsync).mock.calls[0] ?? [];
    expect(shareLocalFile).toHaveBeenCalledWith(uri, { title: "HTML preview", mimeType: "text/html" });
    expect(share()).not.toHaveBeenCalled();
  });

  it("hands a failure on, for the screen to say", async () => {
    jest.mocked(writeAsStringAsync).mockRejectedValueOnce(new Error("disk full"));
    await expect(shareHtmlPreview("<p>hi</p>", "HTML preview")).rejects.toThrow("disk full");

    jest.spyOn(Linking, "openURL").mockRejectedValue(new Error("Unable to open URL"));
    jest.mocked(openBrowserAsync).mockRejectedValue(new Error("Only http and https URLs are supported"));
    jest.mocked(shareLocalFile).mockRejectedValueOnce(new Error("no sheet"));
    await expect(openHtmlInBrowser("<p>hi</p>", "HTML preview")).rejects.toThrow("no sheet");
  });
});

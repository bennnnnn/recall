import * as fileSystem from "expo-file-system/legacy";

import type { PreviewPage } from "@/lib/previewPage";
import {
  forgetPreviewPageFile,
  previewPageFile,
  readyPreviewPageFile,
} from "@/lib/previewPageFile";
import { readVendorLibraries, type VendorLibrary } from "@/lib/vendorAssets";

/** The cache directory as files on disk: path → contents. */
const mockFiles = new Map<string, string>();
const mockStorage = { cacheDirectory: "file:///cache/" as string | null };
const mockHashes: Partial<Record<VendorLibrary, string>> = {};
const mockSources: Partial<Record<VendorLibrary, string>> = {};

jest.mock("expo-file-system/legacy", () => ({
  get cacheDirectory() {
    return mockStorage.cacheDirectory;
  },
  getInfoAsync: jest.fn(async (uri: string) => ({ exists: mockFiles.has(uri) })),
  makeDirectoryAsync: jest.fn(async () => undefined),
  writeAsStringAsync: jest.fn(async (uri: string, contents: string) => {
    mockFiles.set(uri, contents);
  }),
  moveAsync: jest.fn(async ({ from, to }: { from: string; to: string }) => {
    mockFiles.set(to, mockFiles.get(from) ?? "");
    mockFiles.delete(from);
  }),
  readDirectoryAsync: jest.fn(async (dir: string) =>
    [...mockFiles.keys()].filter((uri) => uri.startsWith(dir)).map((uri) => uri.slice(dir.length)),
  ),
  deleteAsync: jest.fn(async (uri: string) => {
    mockFiles.delete(uri);
  }),
}));

jest.mock("expo-crypto", () => {
  const { createHash } = jest.requireActual<{
    createHash(name: string): { update(value: string): { digest(encoding: string): string } };
  }>("node:crypto");
  return {
    CryptoDigestAlgorithm: { SHA256: "SHA-256" },
    digestStringAsync: jest.fn(async (_algorithm: string, value: string) =>
      createHash("sha256").update(value).digest("hex"),
    ),
  };
});

jest.mock("@/lib/vendorAssets", () => ({
  vendorLibraryHash: (library: VendorLibrary) => mockHashes[library],
  readVendorLibraries: jest.fn(async (libraries: VendorLibrary[]) =>
    Object.fromEntries(libraries.map((library) => [library, mockSources[library]])),
  ),
}));

const DIR = "file:///cache/preview-pages/";

/** A fresh page each time: the module keeps one file per page object. */
function mermaidPage(template = "<html>{mermaid}</html>"): PreviewPage<"mermaid"> {
  return {
    name: "mermaid",
    libraries: ["mermaid"],
    build: ({ mermaid }) => template.replace("{mermaid}", mermaid),
  };
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

beforeEach(() => {
  mockFiles.clear();
  mockStorage.cacheDirectory = "file:///cache/";
  mockHashes.mermaid = "3b2f6a";
  mockSources.mermaid = "MERMAID SOURCE";
  jest.clearAllMocks();
});

describe("previewPageFile", () => {
  it("writes the page once and hands every block the same file", async () => {
    const page = mermaidPage();
    expect(readyPreviewPageFile(page)).toBeNull();
    const first = previewPageFile(page);
    const second = previewPageFile(page);
    const uri = await first;

    expect(await second).toBe(uri);
    expect(uri).toMatch(/^file:\/\/\/cache\/preview-pages\/mermaid-[0-9a-f]{16}\.html$/);
    expect(mockFiles.get(uri)).toBe("<html>MERMAID SOURCE</html>");
    expect(readyPreviewPageFile(page)).toBe(uri);
    expect(readVendorLibraries).toHaveBeenCalledTimes(1);
    expect(fileSystem.writeAsStringAsync).toHaveBeenCalledTimes(1);
  });

  it("writes beside the final name, then moves the page into place", async () => {
    const uri = await previewPageFile(mermaidPage());
    expect(fileSystem.writeAsStringAsync).toHaveBeenCalledWith(`${uri}.part`, "<html>MERMAID SOURCE</html>");
    expect(fileSystem.moveAsync).toHaveBeenCalledWith({ from: `${uri}.part`, to: uri });
    expect([...mockFiles.keys()]).toEqual([uri]);
  });

  it("reuses the file an earlier run wrote, without reading the library", async () => {
    const uri = await previewPageFile(mermaidPage());
    jest.clearAllMocks();

    expect(await previewPageFile(mermaidPage())).toBe(uri);
    expect(readVendorLibraries).not.toHaveBeenCalled();
    expect(fileSystem.writeAsStringAsync).not.toHaveBeenCalled();
  });

  it.each([
    ["the page template", () => mermaidPage("<!DOCTYPE html><html>{mermaid}</html>")],
    [
      "the library",
      () => {
        mockHashes.mermaid = "9c41d0";
        mockSources.mermaid = "MERMAID 11";
        return mermaidPage();
      },
    ],
  ])("writes a new file when %s changes and removes the old version", async (_change, next) => {
    const old = await previewPageFile(mermaidPage());
    mockFiles.set(`${DIR}chart-0123456789abcdef.html`, "chart");
    mockFiles.set(`${DIR}mermaid-fedcba9876543210.html.part`, "half a page");

    const uri = await previewPageFile(next());
    await settle();

    expect(uri).not.toBe(old);
    expect([...mockFiles.keys()].sort()).toEqual([`${DIR}chart-0123456789abcdef.html`, uri].sort());
  });

  it("does not keep a failed write, so the next block tries again", async () => {
    const page = mermaidPage();
    jest.mocked(readVendorLibraries).mockRejectedValueOnce(new Error("asset missing"));
    await expect(previewPageFile(page)).rejects.toThrow("asset missing");
    await settle();

    expect(readyPreviewPageFile(page)).toBeNull();
    const uri = await previewPageFile(page);
    expect(mockFiles.get(uri)).toBe("<html>MERMAID SOURCE</html>");
  });

  it("writes the file again after a WebView could not load it", async () => {
    const page = mermaidPage();
    const uri = await previewPageFile(page);
    mockFiles.delete(uri);

    forgetPreviewPageFile(page);
    expect(readyPreviewPageFile(page)).toBeNull();
    expect(await previewPageFile(page)).toBe(uri);
    expect(mockFiles.get(uri)).toBe("<html>MERMAID SOURCE</html>");
  });

  it("fails without a cache directory", async () => {
    mockStorage.cacheDirectory = null;
    await expect(previewPageFile(mermaidPage())).rejects.toThrow("Storage unavailable.");
  });
});

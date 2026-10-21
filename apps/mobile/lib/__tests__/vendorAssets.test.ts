import { Asset } from "expo-asset";
import { readAsStringAsync } from "expo-file-system/legacy";

import {
  readVendorLibraries,
  readVendorLibrary,
  vendorLibraryHash,
  type VendorLibrary,
} from "@/lib/vendorAssets";

/** In this project a required .txt asset is `{ testUri: "<path>" }`; Metro gives a number. */
type TestAsset = { testUri: string };

const mockAsset = { hash: "0f3c9a" as string | null, localUri: "file:///bundle/assets/x.txt" as string | null };
const mockDownloads: string[] = [];

jest.mock("expo-asset", () => ({
  Asset: {
    fromModule: jest.fn((module: TestAsset) => ({
      hash: mockAsset.hash,
      downloadAsync: async () => {
        mockDownloads.push(module.testUri);
        return { localUri: mockAsset.localUri };
      },
    })),
  },
}));

jest.mock("expo-file-system/legacy", () => ({
  readAsStringAsync: jest.fn(async (uri: string) => `source of ${uri}`),
}));

/** The file each library's asset module was required from. */
function assetFile(library: VendorLibrary): string {
  vendorLibraryHash(library);
  const module = jest.mocked(Asset.fromModule).mock.calls.at(-1)?.[0] as unknown as TestAsset;
  return module.testUri.split("/").pop() ?? "";
}

beforeEach(() => {
  mockAsset.hash = "0f3c9a";
  mockAsset.localUri = "file:///bundle/assets/x.txt";
  mockDownloads.length = 0;
  jest.clearAllMocks();
});

describe("vendored library assets", () => {
  it.each([
    ["katexCss", "katex.min.css.txt"],
    ["mermaid", "mermaid.min.js.txt"],
    ["pdf", "pdf.min.js.txt"],
    ["pdfWorker", "pdf.worker.min.js.txt"],
    ["smilesDrawer", "smiles-drawer.min.js.txt"],
    ["vega", "vega.min.js.txt"],
    ["vegaEmbed", "vega-embed.min.js.txt"],
    ["vegaLite", "vega-lite.min.js.txt"],
  ] as const)("ships %s as lib/vendor/%s", (library, file) => {
    expect(assetFile(library)).toBe(file);
  });

  it("knows a library's content hash without reading it", () => {
    expect(vendorLibraryHash("mermaid")).toBe("0f3c9a");
    expect(mockDownloads).toEqual([]);
    expect(readAsStringAsync).not.toHaveBeenCalled();
  });

  it("refuses a library with no content hash", () => {
    mockAsset.hash = null;
    expect(() => vendorLibraryHash("mermaid")).toThrow("no content hash");
  });

  it("reads a library from its file on the device", async () => {
    await expect(readVendorLibrary("katexCss")).resolves.toBe("source of file:///bundle/assets/x.txt");
    expect(mockDownloads).toHaveLength(1);
    expect(readAsStringAsync).toHaveBeenCalledWith("file:///bundle/assets/x.txt");
  });

  it("fails when the asset never reached the device", async () => {
    mockAsset.localUri = null;
    await expect(readVendorLibrary("mermaid")).rejects.toThrow("not on the device");
  });

  it("reads several libraries by name", async () => {
    await expect(readVendorLibraries(["pdf", "pdfWorker"])).resolves.toEqual({
      pdf: "source of file:///bundle/assets/x.txt",
      pdfWorker: "source of file:///bundle/assets/x.txt",
    });
    expect(mockDownloads).toHaveLength(2);
  });
});

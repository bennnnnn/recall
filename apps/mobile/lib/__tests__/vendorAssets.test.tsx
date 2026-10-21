import { act, renderHook } from "@testing-library/react-native";

import { useVendorTexts } from "@/lib/vendorAssets";

const mockDownload = jest.fn(async () => undefined);
const mockRead = jest.fn(async (uri: string) => `text of ${uri}`);
jest.mock("expo-asset", () => ({
  Asset: { fromModule: () => ({ downloadAsync: mockDownload, localUri: "file:///cache/asset.txt", uri: "asset" }) },
}));
jest.mock("expo-file-system/legacy", () => ({
  readAsStringAsync: (uri: string) => mockRead(uri),
}));

/** A fresh module per test: the loader keeps what it read for the run. */
function load(): typeof import("@/lib/vendorAssets") {
  let loaded!: typeof import("@/lib/vendorAssets");
  jest.isolateModules(() => {
    loaded = jest.requireActual<typeof import("@/lib/vendorAssets")>("@/lib/vendorAssets");
  });
  return loaded;
}

beforeEach(() => {
  mockDownload.mockClear();
  mockRead.mockClear();
});

it("reads a library from its bundled asset once per run (DEAD-03)", async () => {
  const vendor = load();
  await expect(vendor.loadVendorText("mermaid")).resolves.toBe("text of file:///cache/asset.txt");
  await vendor.loadVendorText("mermaid");
  expect(mockDownload).toHaveBeenCalledTimes(1);
  expect(mockRead).toHaveBeenCalledTimes(1);
});

it("reads a failed library again next time", async () => {
  const vendor = load();
  mockRead.mockRejectedValueOnce(new Error("unreadable"));
  await expect(vendor.loadVendorText("vega")).rejects.toThrow("unreadable");
  await expect(vendor.loadVendorText("vega")).resolves.toContain("text of");
  expect(mockRead).toHaveBeenCalledTimes(2);
});

it("hands several libraries back by name", async () => {
  const vendor = load();
  await expect(vendor.loadVendorTexts(["pdf", "pdfWorker"])).resolves.toEqual({
    pdf: "text of file:///cache/asset.txt",
    pdfWorker: "text of file:///cache/asset.txt",
  });
});

// The hook runs on the module the renderer shares (an isolated copy has its own React).
it("the hook reads nothing until enabled, then hands the texts over", async () => {
  const { result, rerender } = await renderHook(
    ({ enabled }: { enabled: boolean }) => useVendorTexts(["smilesDrawer"], enabled),
    { initialProps: { enabled: false } },
  );
  expect(result.current).toEqual({ texts: null, failed: false });
  expect(mockRead).not.toHaveBeenCalled();
  await act(async () => { await rerender({ enabled: true }); });
  expect(result.current).toEqual({ texts: { smilesDrawer: "text of file:///cache/asset.txt" }, failed: false });
});

it("the hook says when the libraries could not be read", async () => {
  mockRead.mockRejectedValueOnce(new Error("gone"));
  const { result } = await renderHook(() => useVendorTexts(["katexCss"]));
  await act(async () => {});
  expect(result.current).toEqual({ texts: null, failed: true });
});

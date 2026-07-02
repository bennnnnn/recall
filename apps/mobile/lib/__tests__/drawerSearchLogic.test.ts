import {
  isAbortError,
  shouldApplyDrawerSearchResult,
} from "@/lib/drawerSearchLogic";

describe("drawerSearchLogic", () => {
  it("detects abort errors", () => {
    expect(isAbortError(new DOMException("Aborted", "AbortError"))).toBe(true);
    const err = new Error("Aborted");
    err.name = "AbortError";
    expect(isAbortError(err)).toBe(true);
    expect(isAbortError(new Error("network"))).toBe(false);
  });

  it("applies results only for the latest generation", () => {
    expect(shouldApplyDrawerSearchResult(2, 2)).toBe(true);
    expect(shouldApplyDrawerSearchResult(1, 2)).toBe(false);
  });
});

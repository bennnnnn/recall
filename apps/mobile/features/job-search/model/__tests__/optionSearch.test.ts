import {
  isValidCustomOption,
  matchOption,
  rankedOptions,
} from "@/features/job-search/model/optionSearch";

const FRUITS = ["Apple", "Apricot", "Banana", "Green Apple", "Pineapple"];

describe("rankedOptions", () => {
  it("returns the full list for an empty query (long scrollable sheet)", () => {
    expect(rankedOptions(FRUITS, "")).toEqual(FRUITS);
    expect(rankedOptions(FRUITS, "   ")).toEqual(FRUITS);
  });

  it("ranks prefix, then word-prefix, then substring", () => {
    // "Apple" (prefix) → "Green Apple" (word-prefix) → "Pineapple" (substring)
    expect(rankedOptions(FRUITS, "apple")).toEqual(["Apple", "Green Apple", "Pineapple"]);
  });

  it("excludes already-picked values case-insensitively", () => {
    expect(rankedOptions(FRUITS, "apple", ["apple"])).toEqual(["Green Apple", "Pineapple"]);
    expect(rankedOptions(FRUITS, "", ["Banana"])).toEqual([
      "Apple",
      "Apricot",
      "Green Apple",
      "Pineapple",
    ]);
  });

  it("caps only when a limit is passed", () => {
    expect(rankedOptions(FRUITS, "", [], 2)).toEqual(["Apple", "Apricot"]);
  });
});

describe("matchOption", () => {
  it("matches case-insensitively and returns canonical casing", () => {
    expect(matchOption(FRUITS, "green apple")).toBe("Green Apple");
    expect(matchOption(FRUITS, "  BANANA ")).toBe("Banana");
  });

  it("returns null for unknown or empty input", () => {
    expect(matchOption(FRUITS, "bb")).toBeNull();
    expect(matchOption(FRUITS, "")).toBeNull();
  });
});

describe("isValidCustomOption", () => {
  it("rejects junk like bb", () => {
    expect(isValidCustomOption("bb")).toBe(false);
    expect(isValidCustomOption("x")).toBe(false);
    expect(isValidCustomOption("  ")).toBe(false);
  });

  it("rejects letter-free strings", () => {
    expect(isValidCustomOption("12345")).toBe(false);
    expect(isValidCustomOption("---")).toBe(false);
  });

  it("accepts real custom entries", () => {
    expect(isValidCustomOption("Prompt Engineer")).toBe(true);
    expect(isValidCustomOption("UX Writer")).toBe(true);
  });
});

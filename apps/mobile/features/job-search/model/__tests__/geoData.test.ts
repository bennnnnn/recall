import {
  COUNTRIES,
  matchCountry,
  matchSubdivision,
  searchPlaces,
  SUBDIVISIONS,
} from "@/features/job-search/model/geoData";

describe("COUNTRIES", () => {
  it("covers the world, not just the US", () => {
    // ~195 sovereign states; the ISO list lands just under 250.
    expect(COUNTRIES.length).toBeGreaterThanOrEqual(190);
    for (const country of ["United States", "Ethiopia", "Brazil", "Japan", "Germany", "Nigeria"]) {
      expect(COUNTRIES).toContain(country);
    }
  });

  it("is deduped", () => {
    const lower = COUNTRIES.map((country) => country.toLowerCase());
    expect(new Set(lower).size).toBe(lower.length);
  });
});

describe("matchCountry", () => {
  it("matches case-insensitively with canonical casing", () => {
    expect(matchCountry("united states")).toBe("United States");
    expect(matchCountry(" ETHIOPIA ")).toBe("Ethiopia");
  });

  it("returns null for unknown input", () => {
    expect(matchCountry("bb")).toBeNull();
    expect(matchCountry("")).toBeNull();
  });
});

describe("matchSubdivision", () => {
  it("matches US states case-insensitively", () => {
    expect(matchSubdivision("United States", "texas")).toBe("Texas");
    expect(matchSubdivision("United States", "california")).toBe("California");
  });

  it("returns null for countries without bundled subdivisions", () => {
    expect(matchSubdivision("Ethiopia", "Oromia")).toBeNull();
  });

  it("keeps subdivision lists canonical", () => {
    expect(SUBDIVISIONS["United States"]).toContain("District of Columbia");
    expect(SUBDIVISIONS.Canada).toContain("Quebec");
    expect(SUBDIVISIONS.Australia).toContain("Victoria");
  });
});

describe("searchPlaces", () => {
  it("prefix matches first, then substring", () => {
    const results = searchPlaces(COUNTRIES, "united");
    expect(results).toContain("United States");
    expect(results).toContain("United Kingdom");
    expect(results).toContain("United Arab Emirates");
  });

  it("returns the head of the list for an empty query", () => {
    expect(searchPlaces(COUNTRIES, "", 5)).toEqual(COUNTRIES.slice(0, 5));
  });
});

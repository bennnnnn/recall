import { JOB_TITLES, matchJobTitle, searchJobTitles } from "@/lib/jobSearch/jobTitles";

describe("JOB_TITLES", () => {
  it("is deduped and covers non-tech sectors", () => {
    const lower = JOB_TITLES.map((title) => title.toLowerCase());
    expect(new Set(lower).size).toBe(lower.length);
    // The whole point of the picker: every kind of work, not just software.
    for (const title of [
      "Registered Nurse",
      "Electrician",
      "Chef",
      "Truck Driver",
      "Teacher",
      "Accountant",
      "Hair Stylist",
      "Farmer",
    ]) {
      expect(JOB_TITLES).toContain(title);
    }
  });

  it("includes the everyday words people actually type", () => {
    // Formal titles alone are not enough — "doctor", not just "Physician".
    for (const title of [
      "Doctor",
      "Nurse",
      "Programmer",
      "Software Developer",
      "Driver",
      "Writer",
      "Soldier",
      "Pastor",
      "Judge",
      "Banker",
      "Scientist",
      "Secretary",
      "Realtor",
    ]) {
      expect(JOB_TITLES).toContain(title);
    }
  });

  it("is a long list, not a chip row", () => {
    expect(JOB_TITLES.length).toBeGreaterThanOrEqual(400);
  });
});

describe("searchJobTitles", () => {
  it("returns the full list for an empty query so the sheet is scrollable", () => {
    expect(searchJobTitles("")).toEqual(JOB_TITLES);
  });

  it("ranks prefix matches before substring matches", () => {
    const results = searchJobTitles("soft");
    // Both Software titles prefix-match; anything else is a weaker match.
    expect(results.slice(0, 2)).toEqual(["Software Developer", "Software Engineer"]);
  });

  it("matches word prefixes across separators", () => {
    expect(searchJobTitles("nurse")).toContain("Registered Nurse");
    expect(searchJobTitles("developer")).toContain("Frontend Developer");
  });

  it("excludes already-selected titles", () => {
    const results = searchJobTitles("chef", ["Chef"]);
    expect(results).not.toContain("Chef");
    expect(results).toContain("Sous Chef");
  });
});

describe("matchJobTitle", () => {
  it("matches case-insensitively and returns canonical casing", () => {
    expect(matchJobTitle("registered nurse")).toBe("Registered Nurse");
    expect(matchJobTitle("  CHEF ")).toBe("Chef");
  });

  it("returns null for unknown or empty input", () => {
    expect(matchJobTitle("bb")).toBeNull();
    expect(matchJobTitle("")).toBeNull();
  });
});

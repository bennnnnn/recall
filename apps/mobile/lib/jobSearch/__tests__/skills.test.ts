import { matchSkill, searchSkills, SKILLS } from "@/lib/jobSearch/skills";

describe("SKILLS", () => {
  it("is deduped and covers non-tech work", () => {
    const lower = SKILLS.map((skill) => skill.toLowerCase());
    expect(new Set(lower).size).toBe(lower.length);
    for (const skill of [
      "Welding",
      "CPR",
      "Food Safety",
      "Cash Handling",
      "Forklift Operation",
      "Lesson Planning",
      "Spanish",
      "Hair Cutting",
    ]) {
      expect(SKILLS).toContain(skill);
    }
  });
});

describe("searchSkills", () => {
  it("returns the full list for an empty query", () => {
    expect(searchSkills("")).toEqual(SKILLS);
  });

  it("ranks prefix first and excludes picked skills", () => {
    const results = searchSkills("weld");
    expect(results[0]).toBe("Welding");
    expect(searchSkills("weld", ["Welding"])).toEqual([]);
  });
});

describe("matchSkill", () => {
  it("matches case-insensitively", () => {
    expect(matchSkill("cpr")).toBe("CPR");
    expect(matchSkill("nope")).toBeNull();
  });
});

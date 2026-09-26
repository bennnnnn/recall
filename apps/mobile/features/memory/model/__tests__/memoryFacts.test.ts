import {
  formatMemoryPage,
  joinMemoryFacts,
  parseMemoryPage,
  splitMemoryFacts,
  visibleMemorySections,
} from "@/features/memory/model/memoryFacts";

describe("memoryFacts", () => {
  it("splits on sentence boundaries", () => {
    expect(splitMemoryFacts("Alpha. Gamma.")).toEqual(["Alpha.", "Gamma."]);
  });

  it("BUG FIX: join strips trailing periods so delete-fact cannot invent Alpha..", () => {
    // Naive `facts.join(". ")` on ["Alpha.", "Gamma."] yields "Alpha.. Gamma."
    expect(joinMemoryFacts(["Alpha.", "Gamma."])).toBe("Alpha. Gamma.");
    expect(joinMemoryFacts(["Alpha.", "Gamma."])).not.toContain("..");

    const afterDelete = splitMemoryFacts("Alpha. Gamma.");
    afterDelete.splice(1, 1);
    expect(joinMemoryFacts(afterDelete)).toBe("Alpha.");
  });

  it("rounds a page of sections through one text block", () => {
    const labels = [
      { type: "profile", label: "Profile" },
      { type: "fact", label: "Facts" },
    ];
    const page = formatMemoryPage([
      { label: "Profile", facts: ["The user's name is Bebe", "The user's name is Cal"] },
      { label: "Facts", facts: ["The user has COVID-19"] },
    ]);
    expect(page).toBe(
      "Profile\nThe user's name is Bebe\nThe user's name is Cal\n\nFacts\nThe user has COVID-19",
    );
    expect(parseMemoryPage(page, labels).get("profile")).toEqual([
      "The user's name is Bebe",
      "The user's name is Cal",
    ]);
    expect(parseMemoryPage(page, labels).get("fact")).toEqual(["The user has COVID-19"]);
  });

  it("keeps a short list mounted and hides the tail of a long one", () => {
    const short = [{ type: "fact", facts: [{ text: "One." }, { text: "Two." }] }];
    expect(visibleMemorySections(short).overflows).toBe(false);
    expect(visibleMemorySections(short).sections).toEqual(short);

    const facts = Array.from({ length: 20 }, (_, index) => ({ text: `Fact ${index + 1}` }));
    const folded = visibleMemorySections([{ type: "fact", facts }]);
    expect(folded.overflows).toBe(true);
    expect(folded.sections[0]?.facts.length).toBeLessThan(facts.length);
    expect(folded.sections[0]?.facts.some((fact) => fact.text === "Fact 20")).toBe(false);
  });
});

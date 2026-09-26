import {
  joinMemoryFacts,
  splitMemoryFacts,
  stripMemoryAsOf,
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

  it("drops the server's freshness stamp from a fact", () => {
    expect(stripMemoryAsOf("As of 2026-09-20: Likes short answers")).toBe("Likes short answers");
    expect(stripMemoryAsOf("  Likes tea ")).toBe("Likes tea");
  });
});

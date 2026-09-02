import { learningProjectTitle } from "@/lib/projects/projectUi";

const t = (key: string) => key;

describe("learningProjectTitle", () => {
  it("uses the target language label for vocabulary classes", () => {
    expect(learningProjectTitle("language", t, "English", "en")).toBe("English");
    expect(learningProjectTitle("language", t, "Fallback", "es")).toBe("Español");
  });

  it("treats the vocabulary write alias as a language class", () => {
    expect(learningProjectTitle("vocabulary", t, "x", "es")).toBe("Español");
  });
});

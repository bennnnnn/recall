import { extractImageGenPrompt } from "@/lib/imageGenIntent";

describe("extractImageGenPrompt", () => {
  it("extracts from create a cat pic", () => {
    expect(extractImageGenPrompt("Create a cat pic")).toBe("cat");
  });

  it("extracts from generate image of sunset", () => {
    expect(extractImageGenPrompt("generate image of sunset over mountains")).toBe(
      "sunset over mountains",
    );
  });

  it("extracts from draw me a dog", () => {
    expect(extractImageGenPrompt("draw me a dog")).toBe("dog");
  });

  it("extracts subject-before-noun phrasing", () => {
    expect(extractImageGenPrompt("make a red sports car photo")).toBe("red sports car");
  });

  it("returns null for normal chat", () => {
    expect(extractImageGenPrompt("explain quantum entanglement")).toBeNull();
  });

  it("returns null when attachment context is code-related", () => {
    expect(extractImageGenPrompt("create an image compression script")).toBeNull();
  });

  it("returns null for draw a conclusion", () => {
    expect(extractImageGenPrompt("draw a conclusion from this")).toBeNull();
  });

  it("returns null with pending-style long prompts", () => {
    expect(extractImageGenPrompt("a".repeat(501))).toBeNull();
  });
});

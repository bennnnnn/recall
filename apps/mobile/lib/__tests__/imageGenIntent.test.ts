import { extractImageGenPrompt } from "@/lib/imageGenIntent";

describe("extractImageGenPrompt", () => {
  it("extracts from create a cat pic", () => {
    expect(extractImageGenPrompt("Create a cat pic")).toBe("cat");
  });

  it("extracts from Create cat / create a cat without image noun", () => {
    expect(extractImageGenPrompt("Create cat")).toBe("cat");
    expect(extractImageGenPrompt("create a cat")).toBe("cat");
    expect(extractImageGenPrompt("draw a dog")).toBe("dog");
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

  it("returns null for create-a-todo style app actions", () => {
    expect(extractImageGenPrompt("create a todo")).toBeNull();
    expect(extractImageGenPrompt("make a list")).toBeNull();
    expect(extractImageGenPrompt("create a reminder")).toBeNull();
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

  // Fuzzy heuristic — figurative "draw me a picture" can false-positive.
  // Caller routes Pro matches straight to generation (no confirm sheet).
  it("matches figurative 'draw me a picture' as an image request (known false positive)", () => {
    expect(extractImageGenPrompt("draw me a mental picture of the situation")).toBe(
      "mental picture of the situation",
    );
  });

  it("matches an ambiguous comparison request as an image request (known false positive)", () => {
    expect(extractImageGenPrompt("draw me a comparison between X and Y")).toBe(
      "comparison between X and Y",
    );
  });
});

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

  // This is a fuzzy heuristic and can't perfectly distinguish figurative
  // language ("draw me a picture" as an idiom for "explain") or ambiguous
  // requests from a literal image ask. These cases document real false
  // positives — the caller (useChatSend) must route them through a
  // confirming dialog rather than submitting straight to paid generation,
  // so a false positive here costs a tap to dismiss, not a lost message.
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

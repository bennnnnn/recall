import { extractImageGenPrompt } from "@/lib/imageGenIntent";
import { extractImageLookupQuery } from "@/lib/imageLookupIntent";

describe("extractImageLookupQuery", () => {
  it.each([
    ["Show me ear", "ear"],
    ["show me an ear", "ear"],
    ["show me a golden retriever", "golden retriever"],
    ["Show me the Eiffel Tower", "Eiffel Tower"],
    ["show me a picture of an ear", "ear"],
    ["show me a photo of a shark", "shark"],
    ["show me an image of Mount Everest", "Mount Everest"],
    ["let me see an ear", "ear"],
    ["let me see a golden retriever", "golden retriever"],
    ["what does an ear look like", "ear"],
    ["what does a golden retriever look like", "golden retriever"],
    ["What does a golden retriever look like?", "golden retriever"],
    ["what do octopuses look like", "octopuses"],
  ])("extracts subject from %j", (text, expected) => {
    expect(extractImageLookupQuery(text)).toBe(expected);
  });

  it.each([
    "show me my todos",
    "show me the code",
    "show me an example",
    "show me how to solve this",
    "show me a summary of this chapter",
    "show me my reminders",
    "show me the graph",
    "show me the steps",
    "show me the answer",
    "show me the equation",
    "let me see my notes",
    "what does my code look like",
    "what does the schedule look like",
    "what is a fraction",
    "what's the capital of France",
    "",
    "   ",
    "draw me a cat",
    "create an image of a sunset",
  ])("rejects non-lookup or non-image subject: %j", (text) => {
    expect(extractImageLookupQuery(text)).toBeNull();
  });

  it("rejects overly long message", () => {
    expect(extractImageLookupQuery("show me " + "a".repeat(300))).toBeNull();
  });

  it("rejects overly long subject", () => {
    expect(
      extractImageLookupQuery(
        "show me a very long winded rambling detailed description of a thing",
      ),
    ).toBeNull();
  });

  it("never overlaps with generation intent", () => {
    const lookupOnly = ["show me an ear", "let me see a shark", "what does a cat look like"];
    for (const text of lookupOnly) {
      expect(extractImageLookupQuery(text)).not.toBeNull();
      expect(extractImageGenPrompt(text)).toBeNull();
    }

    const generationOnly = ["draw me a cat", "create an image of a sunset", "Create a cat pic"];
    for (const text of generationOnly) {
      expect(extractImageGenPrompt(text)).not.toBeNull();
      expect(extractImageLookupQuery(text)).toBeNull();
    }
  });
});

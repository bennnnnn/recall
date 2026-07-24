import {
  extractImageGenPrompt,
  extractImageRevisionPrompt,
  imageGenRevisionContext,
  isImageOnlyAssistantContent,
  subjectFromImageGenUserMessage,
} from "@/lib/imageGenIntent";

describe("extractImageGenPrompt", () => {
  it("extracts from create a cat pic", () => {
    expect(extractImageGenPrompt("Create a cat pic")).toBe("cat");
  });

  it("extracts from short draw without an image noun", () => {
    expect(extractImageGenPrompt("draw a dog")).toBe("dog");
  });

  it("does not treat bare make/create as image gen (needs pic/image/photo)", () => {
    expect(extractImageGenPrompt("Create cat")).toBeNull();
    expect(extractImageGenPrompt("create a cat")).toBeNull();
    expect(extractImageGenPrompt("make your own example")).toBeNull();
    expect(extractImageGenPrompt("make an example")).toBeNull();
    expect(extractImageGenPrompt("create a math problem")).toBeNull();
    expect(extractImageGenPrompt("draw me an example")).toBeNull();
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

  it("rejects draw-me comparison (learning/chat, not a picture)", () => {
    expect(extractImageGenPrompt("draw me a comparison between X and Y")).toBeNull();
  });
});

describe("image revision follow-ups", () => {
  it("reads the subject from a Generate image user bubble", () => {
    expect(subjectFromImageGenUserMessage("Generate image: black cat")).toBe("black cat");
  });

  it("detects image-only assistant content", () => {
    expect(
      isImageOnlyAssistantContent("[Image: /attachments/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/file]"),
    ).toBe(true);
    expect(
      isImageOnlyAssistantContent(
        "Here you go\n[Image: /attachments/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/file]",
      ),
    ).toBe(false);
  });

  it("builds a revision prompt after an image-only reply", () => {
    expect(
      extractImageRevisionPrompt("White", {
        lastAssistantIsImageOnly: true,
        previousSubject: "black cat",
      }),
    ).toBe("black cat, White");
    expect(
      extractImageRevisionPrompt("make it blue", {
        lastAssistantIsImageOnly: true,
        previousSubject: "black cat",
      }),
    ).toBe("black cat, blue");
  });

  it("does not treat thanks / normal chat as a revision", () => {
    expect(
      extractImageRevisionPrompt("thanks", {
        lastAssistantIsImageOnly: true,
        previousSubject: "black cat",
      }),
    ).toBeNull();
    expect(
      extractImageRevisionPrompt("White", {
        lastAssistantIsImageOnly: false,
        previousSubject: "black cat",
      }),
    ).toBeNull();
  });

  it("imageGenRevisionContext finds the prior subject", () => {
    expect(
      imageGenRevisionContext([
        {
          id: "u1",
          role: "user",
          content: "Generate image: black cat",
        },
        {
          id: "a1",
          role: "assistant",
          content: "[Image: /attachments/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/file]",
        },
      ]),
    ).toEqual({ lastAssistantIsImageOnly: true, previousSubject: "black cat" });
  });
});

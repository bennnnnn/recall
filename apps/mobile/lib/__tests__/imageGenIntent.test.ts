import {
  extractImageGenPrompt,
  extractImageGenPromptFromThread,
  extractImageRevisionPrompt,
  imageGenRevisionContext,
  isImageOnlyAssistantContent,
  subjectFromImageGenUserMessage,
} from "@/lib/imageGenIntent";
import {
  MATH_CAMERA_PROMPT,
  composerTextAfterMathScanConfirm,
} from "@/lib/mathCameraPrompt";

describe("extractImageGenPrompt", () => {
  it("extracts from create a cat pic", () => {
    expect(extractImageGenPrompt("Create a cat pic")).toBe("cat");
  });

  it("extracts from short draw without an image noun", () => {
    expect(extractImageGenPrompt("draw a dog")).toBe("dog");
    expect(extractImageGenPrompt("draw a mermaid")).toBe("mermaid");
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

  it("does not treat the camera-math caption as image gen", () => {
    expect(extractImageGenPrompt(MATH_CAMERA_PROMPT)).toBeNull();
    expect(extractImageGenPrompt(composerTextAfterMathScanConfirm("x=2"))).toBeNull();
  });

  it("returns null for create-a-todo style app actions", () => {
    expect(extractImageGenPrompt("create a todo")).toBeNull();
    expect(extractImageGenPrompt("make a list")).toBeNull();
    expect(extractImageGenPrompt("create a reminder")).toBeNull();
  });

  it("returns null when attachment context is code-related", () => {
    expect(extractImageGenPrompt("create an image compression script")).toBeNull();
  });

  it("rejects image-noun phrasing whose subject is an app/code thing, not a picture", () => {
    expect(extractImageGenPrompt("generate a picture of the database schema")).toBeNull();
    expect(extractImageGenPrompt("create an image of my todo list")).toBeNull();
    expect(extractImageGenPrompt("make a diagram picture")).toBeNull();
    expect(extractImageGenPrompt("generate a picture of a diagram")).toBeNull();
    expect(extractImageGenPrompt("draw me a diagram")).toBeNull();
    expect(extractImageGenPrompt("Draw a mermaid flowchart for brewing coffee.")).toBeNull();
    expect(extractImageGenPrompt("show me a picture of ways to be smarter")).toBeNull();
    expect(extractImageGenPrompt("create an image of tips for studying")).toBeNull();
  });

  it("returns null for draw a conclusion", () => {
    expect(extractImageGenPrompt("draw a conclusion from this")).toBeNull();
  });

  it("does not generate a picture for verified geometry or chemistry draws", () => {
    expect(extractImageGenPrompt("Draw a right triangle with legs 3 and 4.")).toBeNull();
    expect(extractImageGenPrompt("draw a right triangle with legs 3 and 4")).toBeNull();
    expect(extractImageGenPrompt("draw the molecule caffeine")).toBeNull();
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

  it("reads the subject from the user's original wording", () => {
    expect(subjectFromImageGenUserMessage("create a cat image")).toBe("cat");
    expect(subjectFromImageGenUserMessage("draw me a dog")).toBe("dog");
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
    expect(
      extractImageRevisionPrompt("what's 2+2", {
        lastAssistantIsImageOnly: true,
        previousSubject: "black cat",
      }),
    ).toBeNull();
    expect(
      extractImageRevisionPrompt("help me think", {
        lastAssistantIsImageOnly: true,
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
    ).toEqual({ lastAssistantIsImageOnly: true, previousSubject: "black cat", referenceAttachmentId: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" });
  });

  it("imageGenRevisionContext finds the subject from original wording", () => {
    expect(
      imageGenRevisionContext([
        {
          id: "u1",
          role: "user",
          content: "create a cat image",
        },
        {
          id: "a1",
          role: "assistant",
          content: "[Image: /attachments/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/file]",
        },
      ]),
    ).toEqual({ lastAssistantIsImageOnly: true, previousSubject: "cat", referenceAttachmentId: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" });
  });

  it("imageGenRevisionContext does not treat lookup photos as image-gen", () => {
    expect(
      imageGenRevisionContext([
        {
          id: "u1",
          role: "user",
          content: "Show me a car.",
        },
        {
          id: "a1",
          role: "assistant",
          content: "[Image: /attachments/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/file]",
          model: "image-search-model",
        },
      ]),
    ).toEqual({ lastAssistantIsImageOnly: false, previousSubject: null, referenceAttachmentId: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" });
  });
});

describe("extractImageGenPromptFromThread", () => {
  const user = (id: string, content: string) => ({ id, role: "user" as const, content });

  it("treats Image after Dog as a dog generate", () => {
    expect(extractImageGenPromptFromThread("Image", [user("u1", "Dog")])).toBe("Dog");
    expect(extractImageGenPromptFromThread("a picture", [user("u1", "Dog")])).toBe("Dog");
  });

  it("does not generate a bare Image with no subject", () => {
    expect(extractImageGenPromptFromThread("Image", [])).toBeNull();
    expect(extractImageGenPromptFromThread("Image", [user("u1", "explain gravity")])).toBeNull();
    expect(extractImageGenPromptFromThread("Image", [user("u1", "create a todo")])).toBeNull();
    expect(extractImageGenPromptFromThread("Image", [user("u1", "hi")])).toBeNull();
  });

  it("keeps a one-shot create-a-pic ask", () => {
    expect(extractImageGenPromptFromThread("create a cat pic", [user("u1", "Dog")])).toBe("cat");
  });

  it("generates after that works / do it when the thread already asked for an image", () => {
    const msgs = [user("u1", "Dog"), user("u2", "Image"), user("u3", "U pick")];
    expect(extractImageGenPromptFromThread("That works", msgs)).toBe("Dog");
    expect(extractImageGenPromptFromThread("I said u do it!", msgs)).toBe("Dog");
    expect(extractImageGenPromptFromThread("that works", [user("u1", "add milk")])).toBeNull();
    expect(extractImageGenPromptFromThread("do it", [user("u1", "draw a dog")])).toBe("dog");
  });

  it("does not treat do it as image-gen after the topic moved", () => {
    expect(
      extractImageGenPromptFromThread("do it", [user("u1", "draw a dog"), user("u2", "Paris")]),
    ).toBeNull();
  });
});

import {
  discardDraftAttachment,
  messageTextForSend,
  pastedTextAttachment,
} from "@/features/attachments/model/attachments";
import {
  attachmentDisplayName,
  isPastedText,
  PASTE_MAX_CHARS,
  PASTE_MAX_PAGES,
  PASTED_TEXT_FILE_NAME,
  pastedTextPreview,
} from "@/features/attachments/model/pastedText";

const mockWritten = new Map<string, string>();
const mockDeleted: string[] = [];
const mockDirectories: string[] = [];

jest.mock("@/lib/api", () => ({ api: {} }));
jest.mock("@/features/attachments/api", () => ({ uploadAttachmentBytes: jest.fn() }));
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => 0, requireTokenSession: jest.fn(), SessionChangedError: Error }));
jest.mock("@/ui/overlay/dialogs", () => ({ offerSettings: jest.fn() }));
jest.mock("expo-document-picker", () => ({}));
jest.mock("expo-image-picker", () => ({}));
jest.mock("expo-image-manipulator", () => ({ SaveFormat: { JPEG: "jpeg", PNG: "png", WEBP: "webp" } }));
jest.mock("expo-file-system/legacy", () => ({ cacheDirectory: "file:///cache/" }));
jest.mock("expo-file-system", () => {
  type Part = string | { uri: string };
  class MockDirectory {
    readonly uri: string;
    constructor(parent: { uri: string }, name: string) {
      this.uri = `${parent.uri}${name}/`;
    }
    create() {
      mockDirectories.push(this.uri);
    }
  }
  class MockFile {
    readonly uri: string;
    constructor(...parts: Part[]) {
      this.uri = parts.map((part) => (typeof part === "string" ? part : part.uri)).join("");
    }
    get exists() {
      return mockWritten.has(this.uri);
    }
    create() {
      mockWritten.set(this.uri, "");
    }
    writeSync(text: string) {
      mockWritten.set(this.uri, text);
    }
    delete() {
      mockWritten.delete(this.uri);
      mockDeleted.push(this.uri);
    }
  }
  return { Directory: MockDirectory, File: MockFile, Paths: { cache: { uri: "file:///cache/" } } };
});

beforeEach(() => {
  mockWritten.clear();
  mockDeleted.length = 0;
  mockDirectories.length = 0;
});

describe("text pasted into the composer, as a file to send", () => {
  it("matches the API's name and limits", () => {
    expect(PASTED_TEXT_FILE_NAME).toBe("pasted-text.txt");
    expect(PASTE_MAX_CHARS).toBe(200_000);
    expect(PASTE_MAX_PAGES).toBe(100);
  });

  it("writes the paste to its own file in the cache, and says how long it is and how it starts", () => {
    const text = "Chapter one\n\n  It was a bright cold day in April, " + "and so on. ".repeat(400);
    const attachment = pastedTextAttachment(text);
    expect(mockDirectories).toEqual(["file:///cache/PastedText/"]);
    expect(attachment).toMatchObject({
      kind: "file",
      contentType: "text/plain",
      fileName: PASTED_TEXT_FILE_NAME,
      pasted: { chars: text.length },
    });
    expect(attachment.localUri).toMatch(/^file:\/\/\/cache\/PastedText\/paste-.+\.txt$/);
    expect(mockWritten.get(attachment.localUri)).toBe(text);
    expect(attachment.pasted?.preview.startsWith("Chapter one It was a bright cold day")).toBe(true);
    expect(isPastedText(attachment)).toBe(true);
  });

  it("deletes its file when the draft is dropped", () => {
    const attachment = pastedTextAttachment("x".repeat(3000));
    discardDraftAttachment(null, attachment);
    expect(mockDeleted).toEqual([attachment.localUri]);
  });

  it("sends no made-up request with a paste alone: the text is the message", () => {
    const attachment = pastedTextAttachment("x".repeat(3000));
    expect(messageTextForSend("", attachment)).toBe("");
    expect(messageTextForSend("  What does this say?  ", attachment)).toBe("What does this say?");
    expect(
      messageTextForSend("", { kind: "file", localUri: "file:///a.txt", contentType: "text/plain", fileName: "a.txt" }),
    ).toBe("Summarize this file.");
  });

  it("is told apart by its name and type, and named in the person's language", () => {
    expect(isPastedText({ fileName: PASTED_TEXT_FILE_NAME, contentType: "text/markdown" })).toBe(false);
    expect(isPastedText({ fileName: "notes.txt", contentType: "text/plain" })).toBe(false);
    const t = (key: string) => `t:${key}`;
    expect(attachmentDisplayName(PASTED_TEXT_FILE_NAME, t)).toBe("t:chat.pasted_text");
    expect(attachmentDisplayName("notes.txt", t)).toBe("notes.txt");
  });

  it("previews the opening words on one line", () => {
    expect(pastedTextPreview("  one\ttwo\n\nthree  ")).toBe("one two three");
    expect(pastedTextPreview("z".repeat(5000)).length).toBeLessThanOrEqual(200);
  });
});

import { assetToPending } from "@/features/attachments/model/attachments";
import { MAX_ATTACHMENT_BYTES } from "@/features/attachments/model/attachmentLimits";
import { copyOpenedDocument, openedFileName } from "@/features/attachments/model/openedDocumentCopy";

const SHARED = "content://com.whatsapp.provider.media/item/9";
/** iOS's Inbox copy: a local file. */
const INBOX = "file:///var/mobile/Containers/Data/Application/APP/tmp/com.recall.app-Inbox/Lease.pdf";
/** What Android's module read from the provider, off the JS thread. */
const MEASURED = { name: "Lease.pdf", size: 2048, type: "application/pdf" };

/** The file the other app handed over. */
let mockSource = { exists: true, size: 2048, type: "application/pdf", copyFails: false };
const mockCopies: string[] = [];
const mockCreated: string[] = [];
const mockRemoved: string[] = [];
/** Synchronous reads of the other app's file: on Android each one blocks the JS thread. */
const mockSourceReads: string[] = [];

jest.mock("expo-file-system/legacy", () => ({ cacheDirectory: "file:///cache/" }));
jest.mock("expo-file-system", () => {
  type Part = string | { uri: string };
  class MockDirectory {
    readonly uri: string;
    constructor(parent: { uri: string }, name: string) {
      this.uri = `${parent.uri}${name}/`;
    }
    create() {
      mockCreated.push(this.uri);
    }
  }
  class MockFile {
    readonly uri: string;
    constructor(...parts: Part[]) {
      this.uri = parts.map((part) => (typeof part === "string" ? part : part.uri)).join("");
    }
    private get isCopy() {
      return this.uri.startsWith("file:///cache/");
    }
    get exists() {
      if (this.isCopy) return mockCopies.includes(this.uri);
      mockSourceReads.push("exists");
      return mockSource.exists;
    }
    get size() {
      mockSourceReads.push("size");
      return mockSource.size;
    }
    get type() {
      mockSourceReads.push("type");
      return mockSource.type;
    }
    async copy(to: MockFile) {
      mockCopies.push(to.uri);
      if (mockSource.copyFails) throw new Error("EACCES");
    }
    delete() {
      mockRemoved.push(this.uri);
    }
  }
  return { Directory: MockDirectory, File: MockFile, Paths: { cache: { uri: "file:///cache/" } } };
});
jest.mock("@/features/attachments/model/attachments", () => ({
  assetToPending: jest.fn(async (asset: { uri: string; contentType: string; fileName: string }) => ({
    localUri: asset.uri,
    contentType: asset.contentType,
    fileName: asset.fileName,
    kind: "file",
  })),
}));

beforeEach(() => {
  mockSource = { exists: true, size: 2048, type: "application/pdf", copyFails: false };
  mockCopies.length = 0;
  mockCreated.length = 0;
  mockRemoved.length = 0;
  mockSourceReads.length = 0;
  jest.mocked(assetToPending).mockClear();
});

it("copies the file into the cache folder sign-out clears, then prepares it as a pick", async () => {
  const pending = await copyOpenedDocument(SHARED, MEASURED);

  expect(mockCreated).toEqual(["file:///cache/OpenedFiles/"]);
  expect(mockCopies).toHaveLength(1);
  expect(mockCopies[0]).toMatch(/^file:\/\/\/cache\/OpenedFiles\/opened-[\w-]+\.pdf$/);
  expect(assetToPending).toHaveBeenCalledWith({
    uri: mockCopies[0],
    contentType: "application/pdf",
    fileName: "Lease.pdf",
  });
  expect(pending).toMatchObject({ localUri: mockCopies[0], fileName: "Lease.pdf", kind: "file" });
  // The provider was asked off the JS thread; nothing here reads it synchronously.
  expect(mockSourceReads).toEqual([]);
});

it("refuses a file over the limit before copying it", async () => {
  await expect(copyOpenedDocument(SHARED, { ...MEASURED, size: MAX_ATTACHMENT_BYTES + 1 })).rejects
    .toMatchObject({ reason: "too_large" });
  expect(mockCopies).toEqual([]);
});

it("copies a file whose provider gives no size, for the pick's check to measure", async () => {
  await copyOpenedDocument(SHARED, { name: "Lease.pdf", type: "application/pdf" });
  expect(mockCopies).toHaveLength(1);
  expect(assetToPending).toHaveBeenCalled();
  expect(mockSourceReads).toEqual([]);
});

it("checks iOS's local file itself: its size and type", async () => {
  mockSource.size = MAX_ATTACHMENT_BYTES + 1;
  await expect(copyOpenedDocument(INBOX)).rejects.toMatchObject({ reason: "too_large" });
  mockSource.size = 2048;
  await copyOpenedDocument(INBOX);
  expect(assetToPending).toHaveBeenCalledWith(expect.objectContaining({ contentType: "application/pdf", fileName: "Lease.pdf" }));
});

it("calls an iOS file that is gone unreadable", async () => {
  mockSource.exists = false;
  await expect(copyOpenedDocument(INBOX)).rejects.toMatchObject({ reason: "unreadable" });
  expect(mockCopies).toEqual([]);
});

it("calls a copy that fails unreadable, and leaves no part of it behind", async () => {
  const warn = jest.spyOn(console, "warn").mockImplementation(() => undefined);
  mockSource.copyFails = true;
  await expect(copyOpenedDocument(SHARED, MEASURED)).rejects.toMatchObject({ reason: "unreadable" });
  expect(mockRemoved).toEqual(mockCopies);
  expect(assetToPending).not.toHaveBeenCalled();
  // Logged by kind only: a file system error's text can carry the file's path.
  expect(warn).toHaveBeenCalledWith("[openedFile]", { stage: "copy", error: "Error" });
  warn.mockRestore();
});

describe("openedFileName", () => {
  it.each([
    ["iOS's Inbox copy keeps the original's name", "file:///Documents/Inbox/Lease%20draft.pdf", undefined, "Lease draft.pdf"],
    ["the sharing app's name comes first", SHARED, "Lease.pdf", "Lease.pdf"],
    ["a provider's bare id takes the type's extension", "content://downloads/document/1000123", undefined, "1000123.pdf"],
    ["a name without an extension takes one", SHARED, "Q3 report", "Q3 report.pdf"],
    ["an extension in any case stays", SHARED, "Notes.PDF", "Notes.PDF"],
    ["a name is never a path", SHARED, "../../secret.pdf", ".._.._secret.pdf"],
  ])("%s", (_case, uri, name, expected) => {
    expect(openedFileName(uri, name, "application/pdf")).toBe(expected);
  });

  it("names a file that came with no name at all", () => {
    expect(openedFileName("content://downloads/", "  ", "")).toMatch(/^file-\d+$/);
  });
});

import { AttachmentError } from "@/features/attachments/model/attachmentErrors";
import type { PendingAttachment } from "@/features/attachments/model/attachments";
import { discardLocalCopy } from "@/features/attachments/model/localAttachmentFile";
import {
  claimOpenedDocument,
  clearOpenedDocument,
  isOpenedInboxFile,
  receiveOpenedDocument,
  subscribeOpenedDocument,
} from "@/features/attachments/model/openedDocument";
import { copyOpenedDocument } from "@/features/attachments/model/openedDocumentCopy";

const CONTAINER = "file:///var/mobile/Containers/Data/Application/APP/";
const DOCUMENTS = `${CONTAINER}Documents/`;
/** iOS opens Recall with its Inbox copy, naming the container /private/var/…. */
const OPENED = "file:///private/var/mobile/Containers/Data/Application/APP/Documents/Inbox/Lease%20draft.pdf";
const SECOND = `${DOCUMENTS}Inbox/Invoice.pdf`;
const SHARED = "content://com.whatsapp.provider.media/item/9";
const PDF: PendingAttachment = {
  localUri: "file:///cache/OpenedFiles/opened-1.pdf",
  contentType: "application/pdf",
  fileName: "Lease draft.pdf",
  kind: "file",
};

const mockFiles = new Set<string>();
const mockDeleted: string[] = [];
let mockSession = { generation: 1, signedIn: true };

jest.mock("expo-file-system", () => ({
  Paths: { document: { uri: "file:///var/mobile/Containers/Data/Application/APP/Documents/" } },
  File: class {
    constructor(private readonly uri: string) {}
    get exists() {
      return mockFiles.has(this.uri);
    }
    delete() {
      mockFiles.delete(this.uri);
      mockDeleted.push(this.uri);
    }
  },
}));
jest.mock("@/lib/auth", () => ({
  getSessionGeneration: () => mockSession.generation,
  hasSessionToken: () => mockSession.signedIn,
}));
jest.mock("@/features/attachments/model/openedDocumentCopy", () => ({ copyOpenedDocument: jest.fn() }));
jest.mock("@/features/attachments/model/localAttachmentFile", () => ({ discardLocalCopy: jest.fn() }));

const copy = jest.mocked(copyOpenedDocument);

function signIn(generation: number) {
  mockSession = { generation, signedIn: true };
}

function signOut() {
  mockSession = { generation: mockSession.generation + 1, signedIn: false };
  clearOpenedDocument();
}

beforeEach(() => {
  mockFiles.clear();
  mockFiles.add(OPENED).add(SECOND);
  mockDeleted.length = 0;
  signIn(1);
  copy.mockReset().mockResolvedValue(PDF);
  jest.mocked(discardLocalCopy).mockReset();
});

afterEach(async () => {
  // Whatever a case left held goes, so the next starts with nothing.
  signIn(mockSession.generation);
  copy.mockResolvedValue(PDF);
  await claimOpenedDocument(true);
});

describe("isOpenedInboxFile", () => {
  it.each([
    OPENED,
    SECOND,
    `${DOCUMENTS}Inbox/r%C3%A9sum%C3%A9.pdf`,
    // Newer iOS copies into tmp/ instead.
    `${CONTAINER}tmp/com.recall.app-Inbox/Lease.pdf`,
  ])("knows %s as iOS's Inbox copy", (uri) => {
    expect(isOpenedInboxFile(uri)).toBe(true);
  });

  it.each([
    `${DOCUMENTS}notes.pdf`,
    `${DOCUMENTS}Inbox/`,
    `${DOCUMENTS}Inbox/old/Lease.pdf`,
    `${DOCUMENTS}Inbox/..%2Fnotes.pdf`,
    `${CONTAINER}tmp/Lease.pdf`,
    `${CONTAINER}Library/Caches/Lease.pdf`,
    "file:///var/mobile/Containers/Data/Application/OTHER/Documents/Inbox/Lease.pdf",
    SHARED,
  ])("refuses %s", (uri) => {
    expect(isOpenedInboxFile(uri)).toBe(false);
  });
});

it("reads a file iOS opened Recall with outside the Inbox, and never deletes it: it is the original", async () => {
  const original = "file:///Users/me/Desktop/Lease.pdf";
  receiveOpenedDocument(original);
  expect(await claimOpenedDocument(true)).toBe(PDF);
  expect(copy).toHaveBeenCalledWith(original, undefined);
  expect(mockDeleted).toEqual([]);
});

describe("a file opened while no one is signed in", () => {
  it("waits through sign-in, then goes to whoever signs in once the API confirms them", async () => {
    mockSession = { generation: 1, signedIn: false };
    receiveOpenedDocument(OPENED);
    expect(await claimOpenedDocument(true)).toBeNull();

    signIn(2);
    // A saved sign-in the API has not confirmed yet may still turn out expired.
    expect(await claimOpenedDocument(false)).toBeNull();
    expect(copy).not.toHaveBeenCalled();

    expect(await claimOpenedDocument(true)).toBe(PDF);
    expect(copy).toHaveBeenCalledWith(OPENED, undefined);
    // iOS leaves its Inbox copy for the app to delete.
    expect(mockDeleted).toEqual([OPENED]);
  });

  it("survives the sign-out of a launch whose saved sign-in had expired", async () => {
    mockSession = { generation: 0, signedIn: false };
    receiveOpenedDocument(OPENED);
    signIn(0);
    signOut();
    signIn(2);
    expect(await claimOpenedDocument(true)).toBe(PDF);
  });
});

describe("a file opened while signed in", () => {
  it("goes to that account at once", async () => {
    receiveOpenedDocument(OPENED);
    expect(await claimOpenedDocument(false)).toBe(PDF);
  });

  it("never goes to the next account: sign-out drops it and deletes its Inbox copy", async () => {
    const heard = jest.fn();
    const stop = subscribeOpenedDocument(heard);
    receiveOpenedDocument(OPENED);
    signOut();
    stop();
    expect(heard).toHaveBeenCalledTimes(2);
    expect(mockDeleted).toEqual([OPENED]);

    signIn(3);
    expect(await claimOpenedDocument(true)).toBeNull();
    expect(copy).not.toHaveBeenCalled();
  });

  it("is refused by another account even when no sign-out cleared it", async () => {
    receiveOpenedDocument(OPENED);
    signIn(3);
    expect(await claimOpenedDocument(true)).toBeNull();
    expect(copy).not.toHaveBeenCalled();
    expect(mockDeleted).toEqual([OPENED]);
  });

  it("is dropped, its copy deleted, when the account changes while it is copied", async () => {
    copy.mockImplementation(async () => {
      signIn(4);
      return PDF;
    });
    receiveOpenedDocument(OPENED);
    expect(await claimOpenedDocument(true)).toBeNull();
    expect(discardLocalCopy).toHaveBeenCalledWith(PDF.localUri);
  });

  it("waits while the session holds no token", async () => {
    receiveOpenedDocument(OPENED);
    mockSession = { generation: 1, signedIn: false };
    expect(await claimOpenedDocument(true)).toBeNull();
    signIn(1);
    expect(await claimOpenedDocument(true)).toBe(PDF);
  });
});

it("keeps only the newest file, deleting the Inbox copy of the one it replaces", async () => {
  receiveOpenedDocument(OPENED);
  receiveOpenedDocument(SECOND);
  expect(mockDeleted).toEqual([OPENED]);
  await claimOpenedDocument(true);
  expect(copy).toHaveBeenCalledTimes(1);
  expect(copy).toHaveBeenCalledWith(SECOND, undefined);
});

it("is taken once, however many ask", async () => {
  receiveOpenedDocument(OPENED);
  const [first, second] = await Promise.all([claimOpenedDocument(true), claimOpenedDocument(true)]);
  expect([first, second]).toEqual([PDF, null]);
  expect(copy).toHaveBeenCalledTimes(1);
});

it("ignores a launch read again after its Inbox copy was taken and deleted", async () => {
  mockFiles.delete(OPENED);
  const heard = jest.fn();
  const stop = subscribeOpenedDocument(heard);
  receiveOpenedDocument(OPENED);
  stop();
  expect(heard).not.toHaveBeenCalled();
  expect(await claimOpenedDocument(true)).toBeNull();
});

it("keeps the name Android's sharing app gave a content URI", async () => {
  receiveOpenedDocument(SHARED, "Lease.pdf");
  await claimOpenedDocument(true);
  expect(copy).toHaveBeenCalledWith(SHARED, "Lease.pdf");
  expect(mockDeleted).toEqual([]);
});

it("passes on why a file cannot be attached, and still deletes its Inbox copy", async () => {
  copy.mockRejectedValue(new AttachmentError("too_large"));
  receiveOpenedDocument(OPENED);
  await expect(claimOpenedDocument(true)).rejects.toMatchObject({ reason: "too_large" });
  expect(mockDeleted).toEqual([OPENED]);
});

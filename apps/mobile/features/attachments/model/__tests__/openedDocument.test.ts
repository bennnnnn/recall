import { AttachmentError } from "@/features/attachments/model/attachmentErrors";
import type { PendingAttachment } from "@/features/attachments/model/attachments";
import { discardLocalCopy } from "@/features/attachments/model/localAttachmentFile";
import {
  claimOpenedDocument,
  clearOpenedDocument,
  isOpenedInboxFile,
  receiveOpenedDocument,
  setOpenedDocumentSignIn,
  subscribeOpenedDocument,
  sweepOpenedInboxCopies,
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
const NEWER: PendingAttachment = { ...PDF, localUri: "file:///cache/OpenedFiles/opened-2.pdf", fileName: "Invoice.pdf" };

const mockFiles = new Set<string>();
/** Folder URI → the URIs `list()` returns in it. */
const mockFolders = new Map<string, string[]>();
const mockDeleted: string[] = [];
let mockSession = { generation: 1, signedIn: true };

jest.mock("expo-file-system", () => {
  class MockFile {
    constructor(readonly uri: string) {}
    get exists() {
      return mockFiles.has(this.uri);
    }
    delete() {
      mockFiles.delete(this.uri);
      mockDeleted.push(this.uri);
    }
  }
  class MockDirectory {
    constructor(readonly uri: string) {}
    get exists() {
      return mockFolders.has(this.uri);
    }
    list() {
      return (mockFolders.get(this.uri) ?? []).map((uri) => (uri.endsWith("/") ? new MockDirectory(uri) : new MockFile(uri)));
    }
  }
  return {
    Paths: { document: { uri: "file:///var/mobile/Containers/Data/Application/APP/Documents/" } },
    File: MockFile,
    Directory: MockDirectory,
  };
});
jest.mock("@/lib/auth", () => ({
  getSessionGeneration: () => mockSession.generation,
  hasSessionToken: () => mockSession.signedIn,
}));
jest.mock("@/features/attachments/model/openedDocumentCopy", () => ({ copyOpenedDocument: jest.fn() }));
jest.mock("@/features/attachments/model/localAttachmentFile", () => ({ discardLocalCopy: jest.fn() }));

const copy = jest.mocked(copyOpenedDocument);

/** A sign-in the API has confirmed, as the chat reports it. */
function signIn(generation: number) {
  mockSession = { generation, signedIn: true };
  setOpenedDocumentSignIn(true);
}

/** A saved sign-in read at launch that the API has not answered for yet. */
function restoreUnconfirmed(generation: number) {
  mockSession = { generation, signedIn: true };
  setOpenedDocumentSignIn(false);
}

function signOut() {
  mockSession = { generation: mockSession.generation + 1, signedIn: false };
  clearOpenedDocument();
}

beforeEach(() => {
  mockFiles.clear();
  mockFiles.add(OPENED).add(SECOND);
  mockFolders.clear();
  mockDeleted.length = 0;
  signIn(1);
  copy.mockReset().mockResolvedValue(PDF);
  jest.mocked(discardLocalCopy).mockReset();
});

afterEach(async () => {
  // Whatever a case left held goes, so the next starts with nothing.
  signIn(mockSession.generation);
  copy.mockResolvedValue(PDF);
  await claimOpenedDocument();
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
    `${DOCUMENTS}Inbox/../notes.pdf`,
    `${CONTAINER}tmp/Lease.pdf`,
    `${CONTAINER}Library/Caches/Lease.pdf`,
    "file:///var/mobile/Containers/Data/Application/OTHER/Documents/Inbox/Lease.pdf",
    SHARED,
  ])("refuses %s", (uri) => {
    expect(isOpenedInboxFile(uri)).toBe(false);
  });
});

describe("a file URL iOS opens Recall with", () => {
  it.each([
    `${CONTAINER}Library/Caches/recall-export-1.json`,
    `${DOCUMENTS}notes.pdf`,
    // Dot segments that climb out of the Inbox into Recall's own files.
    `${DOCUMENTS}Inbox/../../Library/Caches/cached-user.json`,
    "file:///var/mobile/Containers/Data/Application/OTHER/../APP/Library/secret.json",
  ])("is never one of Recall's own files: %s", async (uri) => {
    receiveOpenedDocument(uri);
    expect(await claimOpenedDocument()).toBeNull();
    expect(copy).not.toHaveBeenCalled();
  });

  it("outside the container (the Simulator's openurl of a Mac file) is read, never deleted", async () => {
    const original = "file:///Users/me/Desktop/Lease.pdf";
    receiveOpenedDocument(original);
    expect(await claimOpenedDocument()).toBe(PDF);
    expect(copy).toHaveBeenCalledWith(original, {});
    expect(mockDeleted).toEqual([]);
  });
});

describe("a file opened before a sign-in is confirmed", () => {
  it("waits through sign-in, then goes to whoever signs in once the API confirms them", async () => {
    mockSession = { generation: 1, signedIn: false };
    setOpenedDocumentSignIn(false);
    receiveOpenedDocument(OPENED);
    expect(await claimOpenedDocument()).toBeNull();

    restoreUnconfirmed(2);
    expect(await claimOpenedDocument()).toBeNull();
    expect(copy).not.toHaveBeenCalled();

    signIn(2);
    expect(await claimOpenedDocument()).toBe(PDF);
    expect(copy).toHaveBeenCalledWith(OPENED, {});
    // iOS leaves its Inbox copy for the app to delete.
    expect(mockDeleted).toEqual([OPENED]);
  });

  it("survives a saved sign-in that turns out revoked: it arrived while that sign-in held a token", async () => {
    // Android: the module hands the file over once the saved sign-in is read, before /me answers.
    restoreUnconfirmed(0);
    receiveOpenedDocument(SHARED, { name: "Lease.pdf", size: 2048, type: "application/pdf" });
    expect(await claimOpenedDocument()).toBeNull();
    // /me answers 401: the app signs out.
    signOut();
    signIn(2);
    expect(await claimOpenedDocument()).toBe(PDF);
    expect(copy).toHaveBeenCalledWith(SHARED, { name: "Lease.pdf", size: 2048, type: "application/pdf" });
  });
});

describe("a file opened while a confirmed account is signed in", () => {
  it("goes to that account", async () => {
    receiveOpenedDocument(OPENED);
    expect(await claimOpenedDocument()).toBe(PDF);
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
    expect(await claimOpenedDocument()).toBeNull();
    expect(copy).not.toHaveBeenCalled();
  });

  it("is refused by another account even when no sign-out cleared it", async () => {
    receiveOpenedDocument(OPENED);
    signIn(3);
    expect(await claimOpenedDocument()).toBeNull();
    expect(copy).not.toHaveBeenCalled();
    expect(mockDeleted).toEqual([OPENED]);
  });

  it("is dropped, its copy deleted, when the account changes while it is copied", async () => {
    copy.mockImplementation(async () => {
      signIn(4);
      return PDF;
    });
    receiveOpenedDocument(OPENED);
    expect(await claimOpenedDocument()).toBeNull();
    expect(discardLocalCopy).toHaveBeenCalledWith(PDF.localUri);
  });

  it("says nothing when a sign-out during the copy is what failed it", async () => {
    copy.mockImplementation(async () => {
      // Sign-out emptied the cache folder the copy was writing to.
      signOut();
      throw new AttachmentError("unreadable");
    });
    receiveOpenedDocument(OPENED);
    await expect(claimOpenedDocument()).resolves.toBeNull();
  });
});

it("keeps only the newest file, deleting the Inbox copy of the one it replaces", async () => {
  receiveOpenedDocument(OPENED);
  receiveOpenedDocument(SECOND);
  expect(mockDeleted).toEqual([OPENED]);
  await claimOpenedDocument();
  expect(copy).toHaveBeenCalledTimes(1);
  expect(copy).toHaveBeenCalledWith(SECOND, {});
});

it("gives way to a newer file that came while it was copied", async () => {
  let finishFirst: (pending: PendingAttachment) => void = () => undefined;
  copy.mockImplementationOnce(() => new Promise((resolve) => (finishFirst = resolve)));
  copy.mockResolvedValueOnce(NEWER);
  receiveOpenedDocument(OPENED);
  const first = claimOpenedDocument();
  await Promise.resolve();
  receiveOpenedDocument(SECOND);
  const second = await claimOpenedDocument();
  finishFirst(PDF);

  expect(second).toBe(NEWER);
  expect(await first).toBeNull();
  expect(discardLocalCopy).toHaveBeenCalledWith(PDF.localUri);
});

it("is taken once, however many ask", async () => {
  receiveOpenedDocument(OPENED);
  const [first, second] = await Promise.all([claimOpenedDocument(), claimOpenedDocument()]);
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
  expect(await claimOpenedDocument()).toBeNull();
});

it("passes on why a file cannot be attached, and still deletes its Inbox copy", async () => {
  copy.mockRejectedValue(new AttachmentError("too_large"));
  receiveOpenedDocument(OPENED);
  await expect(claimOpenedDocument()).rejects.toMatchObject({ reason: "too_large" });
  expect(mockDeleted).toEqual([OPENED]);
});

describe("sweepOpenedInboxCopies", () => {
  const TMP_INBOX = `${CONTAINER}tmp/com.recall.app-Inbox/`;

  beforeEach(() => {
    mockFolders.set(`${DOCUMENTS}Inbox/`, [OPENED.replace("/private", ""), `${DOCUMENTS}Inbox/old/`]);
    mockFolders.set(`${CONTAINER}tmp/`, [TMP_INBOX, `${CONTAINER}tmp/WebKit/`]);
    mockFolders.set(TMP_INBOX, [`${TMP_INBOX}Left behind.pdf`]);
    mockFolders.set(`${CONTAINER}tmp/WebKit/`, [`${CONTAINER}tmp/WebKit/cache.db`]);
  });

  it("deletes the Inbox copies a killed run left, and nothing else", () => {
    sweepOpenedInboxCopies();
    expect(mockDeleted.sort()).toEqual([`${DOCUMENTS}Inbox/Lease%20draft.pdf`, `${TMP_INBOX}Left behind.pdf`].sort());
  });

  it("keeps the file a cold start is holding", () => {
    receiveOpenedDocument(OPENED);
    sweepOpenedInboxCopies();
    expect(mockDeleted).toEqual([`${TMP_INBOX}Left behind.pdf`]);
  });
});

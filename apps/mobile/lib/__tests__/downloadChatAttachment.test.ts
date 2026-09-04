import { writeAsStringAsync, getInfoAsync, readDirectoryAsync, deleteAsync } from "expo-file-system/legacy";
import * as MediaLibrary from "expo-media-library";
import { Share } from "react-native";

import { fetchAttachmentBase64 } from "@/lib/fetchAttachmentBytes";
import {
  ensureLocalAttachmentFile,
  getCachedAttachmentFile,
  resetLocalAttachmentFileCache,
  clearLocalAttachmentFileCache,
  invalidateCachedAttachmentFile,
  removeCachedAttachmentFiles,
  saveChatAttachmentToLibrary,
  shareChatAttachment,
} from "@/lib/downloadChatAttachment";

jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  EncodingType: { Base64: "base64" },
  writeAsStringAsync: jest.fn(async () => undefined),
  getInfoAsync: jest.fn(async () => ({ exists: true })),
  readDirectoryAsync: jest.fn(async () => []),
  deleteAsync: jest.fn(async () => undefined),
}));

jest.mock("expo-media-library", () => ({
  requestPermissionsAsync: jest.fn(async () => ({ granted: true })),
  saveToLibraryAsync: jest.fn(async () => undefined),
}));

jest.mock("react-native", () => ({
  Platform: { OS: "ios" },
  Share: { share: jest.fn(async () => undefined) },
}));

jest.mock("@/lib/fetchAttachmentBytes", () => ({
  fetchAttachmentBase64: jest.fn(async () => "AAAA"),
}));

jest.mock("@/lib/exportPdf", () => ({
  isShareCancelled: (error: unknown) =>
    error instanceof Error && /did not share/i.test(error.message),
}));

let mockGeneration = 0;
let mockUuid = 0;
jest.mock("@/lib/config", () => ({ getApiUrl: () => "https://api.test" }));
jest.mock("expo-crypto", () => ({ randomUUID: () => `unique-${++mockUuid}` }));
jest.mock("@/lib/auth", () => ({
  getSessionGeneration: () => mockGeneration,
  requireTokenSession: jest.fn(),
  SessionChangedError: class extends Error { constructor() { super("Session changed"); } },
}));

describe("downloadChatAttachment", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetLocalAttachmentFileCache();
    mockGeneration = 0;
    jest.mocked(readDirectoryAsync).mockReset().mockResolvedValue([]);
    jest.mocked(getInfoAsync).mockResolvedValue({ exists: true, isDirectory: false, uri: "file:///cache/a", size: 1, modificationTime: 0 });
  });

  it("caches a remote attachment via authenticated fetch, not downloadAsync", async () => {
    const uri = "http://127.0.0.1:8000/attachments/abc/file";
    const local = await ensureLocalAttachmentFile({
      uri,
      token: "tok",
      fileName: "cat.jpg",
    });

    expect(fetchAttachmentBase64).toHaveBeenCalledWith(uri, "tok");
    expect(writeAsStringAsync).toHaveBeenCalledWith(
      expect.stringContaining("cat.jpg"),
      "AAAA",
      { encoding: "base64" },
    );
    expect(local.startsWith("file://")).toBe(true);
    expect(getCachedAttachmentFile(uri)).toBe(local);

    await ensureLocalAttachmentFile({ uri, token: "tok", fileName: "cat.jpg" });
    expect(fetchAttachmentBase64).toHaveBeenCalledTimes(1);
  });

  it("rejects when the authenticated fetch fails", async () => {
    jest.mocked(fetchAttachmentBase64).mockRejectedValueOnce(new Error("Could not load attachment."));

    await expect(
      ensureLocalAttachmentFile({
        uri: "http://127.0.0.1:8000/attachments/missing/file",
        token: "tok",
        fileName: "missing.jpg",
      }),
    ).rejects.toThrow("Could not load attachment.");
  });

  it("saves to the photo library when permission is granted", async () => {
    const result = await saveChatAttachmentToLibrary({
      uri: "http://127.0.0.1:8000/attachments/abc/file",
      token: "tok",
      fileName: "cat.jpg",
    });
    expect(result).toBe("saved");
    expect(MediaLibrary.saveToLibraryAsync).toHaveBeenCalled();
  });

  it("shares a local file url on iOS", async () => {
    await shareChatAttachment({
      uri: "http://127.0.0.1:8000/attachments/abc/file",
      token: "tok",
      fileName: "cat.jpg",
    });
    expect(Share.share).toHaveBeenCalledWith(
      expect.objectContaining({ url: expect.stringContaining("file://") }),
    );
  });

  it("does not throw when the user dismisses the share sheet", async () => {
    jest.mocked(Share.share).mockRejectedValueOnce(new Error("User did not share"));
    await expect(
      shareChatAttachment({
        uri: "http://127.0.0.1:8000/attachments/abc/file",
        token: "tok",
        fileName: "cat.jpg",
      }),
    ).resolves.toBeUndefined();
  });
  it("keeps different remote files separate even when their URL suffixes match", async () => {
    const suffix = "x".repeat(100);
    const first = await ensureLocalAttachmentFile({ uri: `https://files.test/one?token=${suffix}`, token: "tok", fileName: "image.jpg" });
    const second = await ensureLocalAttachmentFile({ uri: `https://files.test/two?token=${suffix}`, token: "tok", fileName: "image.jpg" });
    expect(first).not.toBe(second);
  });

  it("redownloads a file that the operating system evicted from cache", async () => {
    const uri = "https://files.test/image.jpg";
    await ensureLocalAttachmentFile({ uri, token: "tok" });
    jest.mocked(getInfoAsync).mockResolvedValueOnce({ exists: false, isDirectory: false, uri });
    await ensureLocalAttachmentFile({ uri, token: "tok" });
    expect(fetchAttachmentBase64).toHaveBeenCalledTimes(2);
  });

  it("never returns another account's cached local file", async () => {
    const uri = "https://api.test/attachments/abc/file";
    const first = await ensureLocalAttachmentFile({ uri, token: "tok" });
    mockGeneration++;
    expect(getCachedAttachmentFile(uri)).toBeNull();
    const next = await ensureLocalAttachmentFile({ uri, token: "other-token" });
    expect(next).not.toBe(first);
    expect(fetchAttachmentBase64).toHaveBeenCalledTimes(2);
  });

  it("does not open a share sheet if the account changed while downloading", async () => {
    jest.mocked(fetchAttachmentBase64).mockImplementationOnce(async () => { mockGeneration++; return "AAAA"; });
    await expect(shareChatAttachment({ uri: "https://api.test/attachments/abc/file", token: "tok" }))
      .rejects.toThrow("Session changed");
    expect(Share.share).not.toHaveBeenCalled();
    expect(writeAsStringAsync).not.toHaveBeenCalled();
  });

  it("shares concurrent downloads of the same attachment", async () => {
    const options = { uri: "https://files.test/image.jpg", token: "tok" };
    const [first, second] = await Promise.all([ensureLocalAttachmentFile(options), ensureLocalAttachmentFile(options)]);
    expect(first).toBe(second);
    expect(fetchAttachmentBase64).toHaveBeenCalledTimes(1);
    expect(writeAsStringAsync).toHaveBeenCalledTimes(1);
  });


it("removes a file when logout happens during the disk write", async () => {
  jest.mocked(writeAsStringAsync).mockImplementationOnce(async () => { mockGeneration++; });
  await expect(ensureLocalAttachmentFile({ uri: "https://files.test/late.jpg", token: "tok" }))
    .rejects.toThrow("Session changed");
  expect(deleteAsync).toHaveBeenCalledWith(expect.stringContaining("att-"), { idempotent: true });
  expect(getCachedAttachmentFile("https://files.test/late.jpg")).toBeNull();
});

it("removes tracked cache files during sign-out cleanup", async () => {
  const uri = "https://files.test/logout.jpg";
  const dest = await ensureLocalAttachmentFile({ uri, token: "tok" });
  await clearLocalAttachmentFileCache();
  expect(deleteAsync).toHaveBeenCalledWith(dest, { idempotent: true });
  expect(getCachedAttachmentFile(uri)).toBeNull();
});

it("removes prior-run attachment files after restart without deleting unrelated files or directories", async () => {
  const oldFile = await ensureLocalAttachmentFile({ uri: "https://files.test/prior-run.pdf", token: "tok" });
  resetLocalAttachmentFileCache(); // A cold restart loses all in-memory ownership.
  const legacyName = "att-https___files.test_legacy.pdf-legacy.pdf";
  jest.mocked(readDirectoryAsync).mockResolvedValue([
    oldFile.split("/").pop()!, legacyName, "cached-user.json", "chat-pages", "att-folder", "att-../outside",
  ]);
  jest.mocked(getInfoAsync).mockImplementation(async (uri) => ({
    exists: true, isDirectory: uri.endsWith("att-folder"), uri, size: 1, modificationTime: 0,
  }));

  await clearLocalAttachmentFileCache();

  expect(readDirectoryAsync).toHaveBeenCalledWith("file:///cache/");
  expect(deleteAsync).toHaveBeenCalledTimes(2);
  expect(deleteAsync).toHaveBeenCalledWith(oldFile, { idempotent: true });
  expect(deleteAsync).toHaveBeenCalledWith(`file:///cache/${legacyName}`, { idempotent: true });
});

it("keeps a new session's files when its download completes during logout enumeration", async () => {
  let finishListing!: (names: string[]) => void;
  jest.mocked(readDirectoryAsync).mockImplementationOnce(() => new Promise((resolve) => { finishListing = resolve; }));
  const cleanup = clearLocalAttachmentFileCache();
  mockGeneration++;
  const uri = "https://files.test/new-session.jpg";
  const freshFile = await ensureLocalAttachmentFile({ uri, token: "new-token" });
  finishListing(["att-prior-run.jpg", freshFile.split("/").pop()!]);

  await cleanup;

  expect(deleteAsync).toHaveBeenCalledTimes(1);
  expect(deleteAsync).toHaveBeenCalledWith("file:///cache/att-prior-run.jpg", { idempotent: true });
  expect(getCachedAttachmentFile(uri)).toBe(freshFile);
});

it("still removes remembered files when directory enumeration is unavailable", async () => {
  const file = await ensureLocalAttachmentFile({ uri: "https://files.test/remembered.jpg", token: "tok" });
  jest.mocked(readDirectoryAsync).mockRejectedValueOnce(new Error("Directory unavailable"));
  await clearLocalAttachmentFileCache();
  expect(deleteAsync).toHaveBeenCalledWith(file, { idempotent: true });
});

it("does not save to Photos after switching accounts during the permission prompt", async () => {
  jest.mocked(MediaLibrary.requestPermissionsAsync).mockImplementationOnce(async () => {
    mockGeneration++;
    return { granted: true } as MediaLibrary.PermissionResponse;
  });
  const savedBefore = jest.mocked(MediaLibrary.saveToLibraryAsync).mock.calls.length;
  await expect(saveChatAttachmentToLibrary({ uri: "https://files.test/permission.jpg", token: "tok" }))
    .rejects.toThrow("Session changed");
  expect(MediaLibrary.saveToLibraryAsync).toHaveBeenCalledTimes(savedBefore);
});


it("keeps long filenames within native limits while preserving their extension", async () => {
  const result = await ensureLocalAttachmentFile({ uri: "https://files.test/long-name", token: "tok", fileName: `${"a".repeat(250)}.pdf` });
  expect(result.split("/").pop()!.length).toBeLessThan(256);
  expect(result.endsWith(".pdf")).toBe(true);
});

it("does not reopen a failed share sheet when Photos permission is denied", async () => {
  jest.mocked(MediaLibrary.requestPermissionsAsync).mockResolvedValueOnce({ granted: false } as MediaLibrary.PermissionResponse);
  jest.mocked(Share.share).mockRejectedValueOnce(new Error("Share unavailable"));
  const callsBefore = jest.mocked(Share.share).mock.calls.length;
  await expect(saveChatAttachmentToLibrary({ uri: "https://files.test/share-failure", token: "tok" }))
    .rejects.toThrow("Share unavailable");
  expect(Share.share).toHaveBeenCalledTimes(callsBefore + 1);
});


it("removes all cached variants when an attachment is deleted", async () => {
  const uri = "https://api.test/attachments/deleted/file";
  const original = await ensureLocalAttachmentFile({ uri, token: "tok" });
  const thumbnail = await ensureLocalAttachmentFile({ uri: `${uri}?w=300`, token: "tok" });
  const unrelated = await ensureLocalAttachmentFile({ uri: "https://api.test/attachments/kept/file", token: "tok" });
  await removeCachedAttachmentFiles("deleted");
  expect(getCachedAttachmentFile(uri)).toBeNull();
  expect(getCachedAttachmentFile(`${uri}?w=300`)).toBeNull();
  expect(getCachedAttachmentFile("https://api.test/attachments/kept/file")).toBe(unrelated);
  expect(deleteAsync).toHaveBeenCalledWith(original, { idempotent: true });
  expect(deleteAsync).toHaveBeenCalledWith(thumbnail, { idempotent: true });
});

it("does not restore a deleted attachment when its earlier download completes", async () => {
  const uri = "https://api.test/attachments/deleted/file";
  let resolveBytes!: (value: string) => void;
  jest.mocked(fetchAttachmentBase64).mockImplementationOnce(() => new Promise((resolve) => { resolveBytes = resolve; }));
  const download = ensureLocalAttachmentFile({ uri, token: "tok" });
  const rejected = expect(download).rejects.toThrow("Attachment changed");
  await removeCachedAttachmentFiles("deleted");
  resolveBytes("OLD");
  await rejected;
  expect(getCachedAttachmentFile(uri)).toBeNull();
  expect(writeAsStringAsync).not.toHaveBeenCalled();
});

it("starts a fresh retry and ignores the invalidated in-flight preview", async () => {
  const uri = "https://api.test/attachments/retry/file";
  let resolveBytes!: (value: string) => void;
  jest.mocked(fetchAttachmentBase64).mockImplementationOnce(() => new Promise((resolve) => { resolveBytes = resolve; }));
  const first = ensureLocalAttachmentFile({ uri, token: "tok" });
  const rejected = expect(first).rejects.toThrow("Attachment changed");
  invalidateCachedAttachmentFile(uri);
  const retry = await ensureLocalAttachmentFile({ uri, token: "tok" });
  resolveBytes("OLD");
  await rejected;
  expect(fetchAttachmentBase64).toHaveBeenCalledTimes(2);
  expect(getCachedAttachmentFile(uri)).toBe(retry);
  expect(writeAsStringAsync).toHaveBeenCalledTimes(1);
  expect(writeAsStringAsync).toHaveBeenCalledWith(retry, "AAAA", { encoding: "base64" });
});
});

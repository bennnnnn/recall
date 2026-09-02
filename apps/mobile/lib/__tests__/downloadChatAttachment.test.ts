jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  EncodingType: { Base64: "base64" },
  writeAsStringAsync: jest.fn(async () => undefined),
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

import { writeAsStringAsync } from "expo-file-system/legacy";
import * as MediaLibrary from "expo-media-library";
import { Share } from "react-native";

import { fetchAttachmentBase64 } from "@/lib/fetchAttachmentBytes";
import {
  ensureLocalAttachmentFile,
  getCachedAttachmentFile,
  resetLocalAttachmentFileCache,
  saveChatAttachmentToLibrary,
  shareChatAttachment,
} from "@/lib/downloadChatAttachment";

describe("downloadChatAttachment", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetLocalAttachmentFileCache();
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
});

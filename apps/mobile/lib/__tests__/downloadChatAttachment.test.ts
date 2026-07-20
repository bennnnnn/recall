jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  downloadAsync: jest.fn(async (_uri: string, dest: string) => ({
    uri: dest,
    status: 200,
  })),
}));

jest.mock("expo-media-library", () => ({
  requestPermissionsAsync: jest.fn(async () => ({ granted: true })),
  saveToLibraryAsync: jest.fn(async () => undefined),
}));

jest.mock("react-native", () => ({
  Platform: { OS: "ios" },
  Share: { share: jest.fn(async () => undefined) },
}));

import { downloadAsync } from "expo-file-system/legacy";
import * as MediaLibrary from "expo-media-library";
import { Share } from "react-native";

import {
  ensureLocalAttachmentFile,
  getCachedAttachmentFile,
  saveChatAttachmentToLibrary,
  shareChatAttachment,
} from "@/lib/downloadChatAttachment";

describe("downloadChatAttachment", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("caches a remote attachment with auth headers via downloadAsync", async () => {
    const uri = "http://127.0.0.1:8000/attachments/abc/file";
    const local = await ensureLocalAttachmentFile({
      uri,
      token: "tok",
      fileName: "cat.jpg",
    });

    expect(downloadAsync).toHaveBeenCalledWith(
      uri,
      expect.stringContaining("cat.jpg"),
      { headers: { Authorization: "Bearer tok" } },
    );
    expect(local.startsWith("file://")).toBe(true);
    expect(getCachedAttachmentFile(uri)).toBe(local);

    // Second call hits memory cache — no second download.
    await ensureLocalAttachmentFile({ uri, token: "tok", fileName: "cat.jpg" });
    expect(downloadAsync).toHaveBeenCalledTimes(1);
  });

  it("rejects when downloadAsync returns a non-2xx status", async () => {
    jest.mocked(downloadAsync).mockResolvedValueOnce({
      uri: "file:///cache/missing.jpg",
      status: 404,
    } as Awaited<ReturnType<typeof downloadAsync>>);

    await expect(
      ensureLocalAttachmentFile({
        uri: "http://127.0.0.1:8000/attachments/missing/file",
        token: "tok",
        fileName: "missing.jpg",
      }),
    ).rejects.toThrow("Download failed.");
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
});

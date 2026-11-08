const platform = { OS: "ios" };

jest.mock("react-native", () => ({
  Platform: platform,
  Share: {
    share: jest.fn(),
    sharedAction: "sharedAction",
    dismissedAction: "dismissedAction",
  },
}));

jest.mock("expo-print", () => ({
  printToFileAsync: jest.fn(),
}));

jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  EncodingType: { UTF8: "utf8" },
  makeDirectoryAsync: jest.fn(async () => undefined),
  writeAsStringAsync: jest.fn(async () => undefined),
  readDirectoryAsync: jest.fn(async () => []),
  deleteAsync: jest.fn(async () => undefined),
  getInfoAsync: jest.fn(),
}));
jest.mock("@/lib/shareFile", () => ({ ...jest.requireActual("@/lib/shareFile"), shareLocalFile: jest.fn() }));

import { Platform, Share } from "react-native";

import { presentShareSheet } from "@/lib/share";

const { writeAsStringAsync } = jest.requireMock<{ writeAsStringAsync: jest.Mock }>("expo-file-system/legacy");
const { shareLocalFile } = jest.requireMock<{ shareLocalFile: jest.Mock }>("@/lib/shareFile");

describe("share sheet", () => {
  beforeEach(() => {
    platform.OS = "ios";
    shareLocalFile.mockReset();
    writeAsStringAsync.mockClear();
    jest.mocked(Share.share).mockReset();
    jest.mocked(Share.share).mockResolvedValue({ action: Share.sharedAction, activityType: undefined });
  });

  it("opens the native share sheet with message and iOS subject", async () => {
    await presentShareSheet({ message: "Hello thread", title: "My chat" });
    expect(Share.share).toHaveBeenCalledWith(
      { message: "Hello thread", title: "My chat" },
      { subject: "My chat" },
    );
  });

  it("uses dialogTitle on Android", async () => {
    Platform.OS = "android";
    await presentShareSheet({ message: "Hello thread", title: "My chat" });
    expect(Share.share).toHaveBeenCalledWith(
      { message: "Hello thread", title: "My chat" },
      { dialogTitle: "My chat" },
    );
  });

  it("does not throw when the user dismisses the sheet", async () => {
    jest.mocked(Share.share).mockRejectedValueOnce(new Error("User did not share"));
    await expect(
      presentShareSheet({ message: "Hello thread", title: "My chat" }),
    ).resolves.toBeUndefined();
  });

  // Android hands shared text over inside the share intent, which a very long chat
  // overflows (the 1 MB Binder buffer): the share failed as "Could not share this chat".
  it("sends a very long text on Android as a .txt file named after it", async () => {
    Platform.OS = "android";
    const message = "x".repeat(100_001);
    await presentShareSheet({ message, title: "Spanish: verbs" });
    expect(Share.share).not.toHaveBeenCalled();
    const [file, text] = writeAsStringAsync.mock.calls[0] ?? [];
    expect(text).toBe(message);
    expect(String(file)).toMatch(/^file:\/\/\/cache\/recall-share-[\d-]+\/Spanish%20verbs\.txt$/);
    expect(shareLocalFile).toHaveBeenCalledWith(file, { title: "Spanish: verbs", mimeType: "text/plain" });
  });

  it.each([
    ["Android, under the limit", "android", 100_000],
    ["iOS, however long", "ios", 300_000],
  ])("keeps the text as text on %s", async (_case, os, length) => {
    platform.OS = os;
    await presentShareSheet({ message: "x".repeat(length), title: "Long chat" });
    expect(Share.share).toHaveBeenCalledTimes(1);
    expect(shareLocalFile).not.toHaveBeenCalled();
  });

  it("rejects an empty payload instead of opening a blank sheet", async () => {
    await expect(presentShareSheet({ message: "   " })).rejects.toThrow("share_empty");
    expect(Share.share).not.toHaveBeenCalled();
  });
});

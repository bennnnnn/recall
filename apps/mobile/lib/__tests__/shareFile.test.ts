import { shareAsync } from "expo-sharing";
import { Platform, Share } from "react-native";

import { shareLocalFile, shareOneAtATime, shareRoute } from "@/lib/shareFile";
import { shareFailureKey, SharingUnavailableError } from "@/lib/shareUnavailable";

jest.mock("react-native", () => ({
  Platform: { OS: "ios" },
  Share: { share: jest.fn(async () => undefined) },
}));

// expo-sharing is loaded only when its native module is in the build.
let mockHasSharing = true;
jest.mock("expo-modules-core", () => ({
  requireOptionalNativeModule: (name: string) => (name === "ExpoSharing" && mockHasSharing ? {} : null),
}));
jest.mock("expo-sharing", () => ({ shareAsync: jest.fn(async () => undefined) }));

beforeEach(() => {
  jest.clearAllMocks();
  mockHasSharing = true;
  (Platform as { OS: string }).OS = "ios";
});

it.each([
  ["ios", true, "expo-sharing"],
  ["android", true, "expo-sharing"],
  ["ios", false, "rn-share"],
  ["android", false, "unavailable"],
] as const)("on %s with expo-sharing=%s shares through %s", (platform, hasSharing, route) => {
  expect(shareRoute(platform, hasSharing)).toBe(route);
});

it("hands the file, its type and its title to expo-sharing", async () => {
  (Platform as { OS: string }).OS = "android";
  await shareLocalFile("file:///cache/a.pdf", {
    title: "a.pdf",
    mimeType: "application/pdf",
    uti: "com.adobe.pdf",
  });
  expect(shareAsync).toHaveBeenCalledWith("file:///cache/a.pdf", {
    dialogTitle: "a.pdf",
    mimeType: "application/pdf",
    UTI: "com.adobe.pdf",
  });
  expect(Share.share).not.toHaveBeenCalled();
});

it.each([
  ["file:///cache/recall-share-1-2/photo.jpg", { mimeType: "image/jpeg" }],
  ["file:///cache/Print/Scan.PDF", { mimeType: "application/pdf", uti: "com.adobe.pdf" }],
])("on iOS declares no type for %s, which expo-sharing would name again (photo.jpg.jpeg)", async (uri, type) => {
  await shareLocalFile(uri, { title: "t", ...type });
  expect(shareAsync).toHaveBeenCalledWith(uri, { dialogTitle: "t" });
});

it("on iOS declares the type of a file with no extension, so it does not open as plain data", async () => {
  await shareLocalFile("file:///cache/recall-share-1-2/notes", { title: "notes", mimeType: "text/markdown" });
  expect(shareAsync).toHaveBeenCalledWith("file:///cache/recall-share-1-2/notes", {
    dialogTitle: "notes",
    mimeType: "text/markdown",
  });
});

it("falls back to a file url on iOS builds without expo-sharing", async () => {
  mockHasSharing = false;
  await shareLocalFile("file:///cache/a.pdf", { title: "a.pdf" });
  expect(Share.share).toHaveBeenCalledWith({ url: "file:///cache/a.pdf", title: "a.pdf" });
});

it("refuses to share a path as text on Android builds without expo-sharing", async () => {
  mockHasSharing = false;
  (Platform as { OS: string }).OS = "android";
  const error = await shareLocalFile("file:///cache/a.pdf", { title: "a.pdf" }).catch((failure: unknown) => failure);
  expect(error).toBeInstanceOf(SharingUnavailableError);
  expect(shareFailureKey(error, "common.share_failed")).toBe("common.share_needs_update");
  expect(Share.share).not.toHaveBeenCalled();
});

it("keeps the caller's line for any other share failure", () => {
  expect(shareFailureKey(new Error("Sharing files needs an app update."), "common.share_failed")).toBe("common.share_failed");
  expect(shareFailureKey(new Error("boom"), null)).toBeNull();
});

it("treats a dismissed sheet as done", async () => {
  jest.mocked(shareAsync).mockRejectedValueOnce(new Error("User did not share"));
  await expect(shareLocalFile("file:///cache/a.pdf", { title: "a.pdf" })).resolves.toBeUndefined();
});

// Android's share module takes one request until its sheet closes and refused a second
// tap's ("Another share request is being processed now"): the screen said the share failed.
describe("one file share at a time", () => {
  it("drops a share asked for while one runs, then takes the next once it is done", async () => {
    let close: () => void = () => {};
    const first = jest.fn(() => new Promise<void>((resolve) => { close = resolve; }));
    const second = jest.fn(async () => undefined);
    const running = shareOneAtATime(first);
    await expect(shareOneAtATime(second)).resolves.toBe(false);
    expect(second).not.toHaveBeenCalled();
    close();
    await expect(running).resolves.toBe(true);
    await expect(shareOneAtATime(second)).resolves.toBe(true);
    expect(second).toHaveBeenCalledTimes(1);
  });

  it("hands a failure on and frees the next share", async () => {
    await expect(shareOneAtATime(async () => { throw new Error("boom"); })).rejects.toThrow("boom");
    const next = jest.fn(async () => undefined);
    await expect(shareOneAtATime(next)).resolves.toBe(true);
  });
});

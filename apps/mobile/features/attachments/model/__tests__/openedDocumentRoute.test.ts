import { receiveOpenedDocument } from "@/features/attachments/model/openedDocument";
import { redirectSystemPath } from "@/features/attachments/model/openedDocumentRoute";

const INBOX_FILE = "file:///private/var/mobile/Containers/Data/Application/APP/tmp/com.recall.app-Inbox/Lease.pdf";

const mockPlatform = { OS: "ios" };
jest.mock("react-native", () => ({
  get Platform() {
    return mockPlatform;
  },
}));
jest.mock("@/features/attachments/model/openedDocument", () => ({ receiveOpenedDocument: jest.fn() }));

beforeEach(() => {
  jest.mocked(receiveOpenedDocument).mockReset();
  mockPlatform.OS = "ios";
});

it.each([
  "recall://chat?chatId=chat-1",
  "/settings/profile",
  "https://recall.app/share",
  "exp+recall://expo-development-client/?url=http%3A%2F%2F10.0.0.2%3A8081",
])("routes %s as it came", (path) => {
  expect(redirectSystemPath({ path, initial: true })).toBe(path);
  expect(redirectSystemPath({ path, initial: false })).toBe(path);
  expect(receiveOpenedDocument).not.toHaveBeenCalled();
});

it("holds the file iOS opened Recall with: a launch opens on the chat, a running app stays put", () => {
  expect(redirectSystemPath({ path: INBOX_FILE, initial: true })).toBe("/");
  expect(redirectSystemPath({ path: INBOX_FILE, initial: false })).toBeNull();
  expect(receiveOpenedDocument).toHaveBeenNthCalledWith(1, INBOX_FILE);
  expect(receiveOpenedDocument).toHaveBeenNthCalledWith(2, INBOX_FILE);
});

it("keeps Android's content URL off the router; the opened-document module reads it with its name", () => {
  mockPlatform.OS = "android";
  const path = "content://com.android.providers.downloads.documents/document/42";
  expect(redirectSystemPath({ path, initial: true })).toBe("/");
  expect(redirectSystemPath({ path, initial: false })).toBeNull();
  expect(receiveOpenedDocument).not.toHaveBeenCalled();
});

it("never holds a file URL on Android, where one could name Recall's own files", () => {
  mockPlatform.OS = "android";
  const path = "FILE:///data/user/0/com.recall.app/files/secret.json";
  expect(redirectSystemPath({ path, initial: true })).toBe("/");
  expect(receiveOpenedDocument).not.toHaveBeenCalled();
});

it("still opens the chat when the file cannot be held", () => {
  const warn = jest.spyOn(console, "warn").mockImplementation(() => undefined);
  jest.mocked(receiveOpenedDocument).mockImplementation(() => {
    throw new Error("unreadable container");
  });
  expect(redirectSystemPath({ path: INBOX_FILE, initial: true })).toBe("/");
  expect(warn).toHaveBeenCalledWith("[openedFile]", { stage: "receive", error: "Error" });
  warn.mockRestore();
});

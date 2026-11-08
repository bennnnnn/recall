import { receiveOpenedDocument } from "@/features/attachments/model/openedDocument";
import { redirectSystemPath } from "@/features/attachments/model/openedDocumentRoute";

const INBOX_FILE = "file:///private/var/mobile/Containers/Data/Application/APP/Documents/Inbox/Lease.pdf";

jest.mock("@/features/attachments/model/openedDocument", () => ({
  isOpenedInboxFile: (uri: string) => uri.includes("/Documents/Inbox/"),
  receiveOpenedDocument: jest.fn(),
}));

beforeEach(() => jest.mocked(receiveOpenedDocument).mockReset());

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

it("holds iOS's Inbox copy for New chat: a launch opens on the chat, a running app stays put", () => {
  expect(redirectSystemPath({ path: INBOX_FILE, initial: true })).toBe("/");
  expect(redirectSystemPath({ path: INBOX_FILE, initial: false })).toBeNull();
  expect(receiveOpenedDocument).toHaveBeenNthCalledWith(1, INBOX_FILE);
  expect(receiveOpenedDocument).toHaveBeenNthCalledWith(2, INBOX_FILE);
});

it("keeps Android's content URL off the router; the opened-document module reads it with its name", () => {
  const path = "content://com.android.providers.downloads.documents/document/42";
  expect(redirectSystemPath({ path, initial: true })).toBe("/");
  expect(redirectSystemPath({ path, initial: false })).toBeNull();
  expect(receiveOpenedDocument).not.toHaveBeenCalled();
});

it("never routes another file URL, and never holds it", () => {
  const path = "FILE:///var/mobile/Containers/Data/Application/APP/Library/Caches/x.pdf";
  expect(redirectSystemPath({ path, initial: true })).toBe("/");
  expect(redirectSystemPath({ path, initial: false })).toBeNull();
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

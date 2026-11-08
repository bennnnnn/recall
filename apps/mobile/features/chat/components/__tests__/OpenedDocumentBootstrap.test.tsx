import { act, render } from "@testing-library/react-native";

import { watchAndroidOpenedDocuments } from "@/features/attachments/model/androidOpenedDocuments";
import { AttachmentError } from "@/features/attachments/model/attachmentErrors";
import type { PendingAttachment } from "@/features/attachments/model/attachments";
import { claimOpenedDocument, receiveOpenedDocument } from "@/features/attachments/model/openedDocument";
import { copyOpenedDocument } from "@/features/attachments/model/openedDocumentCopy";
import {
  resetComposerAttachmentQueue,
  takeQueuedComposerAttachment,
} from "@/features/attachments/model/pendingComposerAttachment";
import { OpenedDocumentBootstrap } from "@/features/chat/components/OpenedDocumentBootstrap";
import { closeDrawer, startNewChatGlobal } from "@/features/chat/drawer/drawer";

/** iOS's Inbox copy of a PDF opened in Recall from Files. */
const OPENED = "file:///var/mobile/Containers/Data/Application/APP/Documents/Inbox/Lease.pdf";
const PDF: PendingAttachment = {
  localUri: "file:///cache/OpenedFiles/opened-1.pdf",
  contentType: "application/pdf",
  fileName: "Lease.pdf",
  kind: "file",
};

let mockSession = { generation: 1, signedIn: true };
let mockAuth: { token: string | null; profileValidated: boolean } = { token: "token-a", profileValidated: true };
let mockOffline = false;
let mockPathname = "/";
let mockParams: { chatId?: string } = {};
const mockDismissTo = jest.fn();
const mockError = jest.fn();
const mockStopWatching = jest.fn();

jest.mock("expo-file-system", () => ({
  Paths: { document: { uri: "file:///var/mobile/Containers/Data/Application/APP/Documents/" } },
  File: class {
    readonly exists = true;
    delete() {}
  },
}));
jest.mock("expo-router", () => ({
  useRouter: () => ({ dismissTo: mockDismissTo }),
  usePathname: () => mockPathname,
  useGlobalSearchParams: () => mockParams,
}));
jest.mock("@/lib/auth", () => ({
  getSessionGeneration: () => mockSession.generation,
  hasSessionToken: () => mockSession.signedIn,
}));
jest.mock("@/contexts/AuthContext", () => ({ useAuthOptional: () => mockAuth }));
jest.mock("@/contexts/NetworkContext", () => ({ useNetwork: () => ({ isOffline: mockOffline, status: "online" }) }));
jest.mock("@/contexts/ActionFeedbackContext", () => ({ useActionFeedbackOptional: () => ({ error: mockError }) }));
jest.mock("@/features/attachments/model/androidOpenedDocuments", () => ({
  watchAndroidOpenedDocuments: jest.fn(() => mockStopWatching),
}));
jest.mock("@/features/attachments/model/openedDocumentCopy", () => ({ copyOpenedDocument: jest.fn() }));
jest.mock("@/features/attachments/model/localAttachmentFile", () => ({ discardLocalCopy: jest.fn() }));
jest.mock("@/features/chat/drawer/drawer", () => ({ closeDrawer: jest.fn(), startNewChatGlobal: jest.fn() }));

const copy = jest.mocked(copyOpenedDocument);

/** Lets the claim's copy settle and the component's effects run. */
async function settle(): Promise<void> {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

async function open(uri = OPENED): Promise<void> {
  await act(async () => receiveOpenedDocument(uri));
  await settle();
}

function signIn(generation: number, profileValidated = true) {
  mockSession = { generation, signedIn: true };
  mockAuth = { token: `token-${generation}`, profileValidated };
}

beforeEach(() => {
  jest.clearAllMocks();
  resetComposerAttachmentQueue();
  signIn(1);
  mockOffline = false;
  mockPathname = "/";
  mockParams = {};
  copy.mockResolvedValue(PDF);
});

afterEach(async () => {
  // Whatever a case left held goes, so the next starts with nothing.
  signIn(mockSession.generation);
  await claimOpenedDocument(true);
});

it("holds a file opened while signed out through sign-in, then puts it in New chat's composer", async () => {
  mockSession = { generation: 1, signedIn: false };
  mockAuth = { token: null, profileValidated: false };
  mockPathname = "/login";
  const screen = await render(<OpenedDocumentBootstrap />);
  await open();
  expect(copy).not.toHaveBeenCalled();
  expect(takeQueuedComposerAttachment("new")).toBeNull();

  signIn(2);
  await screen.rerender(<OpenedDocumentBootstrap />);
  await settle();

  expect(copy).toHaveBeenCalledWith(OPENED, undefined);
  expect(takeQueuedComposerAttachment("new")).toBe(PDF);
  // The sign-in flow ends on New chat by itself: nothing is pushed over it.
  expect(mockDismissTo).not.toHaveBeenCalled();
  expect(startNewChatGlobal).not.toHaveBeenCalled();
});

it("on another chat, starts New chat with the file in its composer", async () => {
  mockParams = { chatId: "chat-1" };
  await render(<OpenedDocumentBootstrap />);
  await open();

  expect(takeQueuedComposerAttachment("chat-1")).toBeNull();
  expect(takeQueuedComposerAttachment("new")).toBe(PDF);
  expect(closeDrawer).toHaveBeenCalled();
  expect(startNewChatGlobal).toHaveBeenCalledTimes(1);
});

it("on New chat, only fills the composer", async () => {
  await render(<OpenedDocumentBootstrap />);
  await open();
  expect(takeQueuedComposerAttachment("new")).toBe(PDF);
  expect(startNewChatGlobal).not.toHaveBeenCalled();
  expect(mockDismissTo).not.toHaveBeenCalled();
});

it("from another screen, goes back to the chat, whose open chat gives way to New chat", async () => {
  mockPathname = "/settings/profile";
  const screen = await render(<OpenedDocumentBootstrap />);
  await open();
  expect(mockDismissTo).toHaveBeenCalledWith("/");
  expect(startNewChatGlobal).not.toHaveBeenCalled();

  mockPathname = "/";
  mockParams = { chatId: "chat-1" };
  await screen.rerender(<OpenedDocumentBootstrap />);
  expect(startNewChatGlobal).toHaveBeenCalledTimes(1);

  // Only the return it caused: a later visit to that chat stays on it.
  mockPathname = "/settings";
  await screen.rerender(<OpenedDocumentBootstrap />);
  mockPathname = "/";
  await screen.rerender(<OpenedDocumentBootstrap />);
  expect(startNewChatGlobal).toHaveBeenCalledTimes(1);
});

it("waits for the API to confirm a saved sign-in before taking a file that came before it", async () => {
  mockSession = { generation: 0, signedIn: false };
  mockAuth = { token: null, profileValidated: false };
  const screen = await render(<OpenedDocumentBootstrap />);
  await open();

  // The launch read the saved sign-in; the API has not answered yet.
  signIn(0, false);
  await screen.rerender(<OpenedDocumentBootstrap />);
  await settle();
  expect(copy).not.toHaveBeenCalled();

  signIn(0, true);
  await screen.rerender(<OpenedDocumentBootstrap />);
  await settle();
  expect(takeQueuedComposerAttachment("new")).toBe(PDF);
});

it("takes it offline too, where the API cannot confirm the saved sign-in", async () => {
  mockSession = { generation: 0, signedIn: false };
  const screen = await render(<OpenedDocumentBootstrap />);
  await open();
  signIn(0, false);
  mockOffline = true;
  await screen.rerender(<OpenedDocumentBootstrap />);
  await settle();
  expect(takeQueuedComposerAttachment("new")).toBe(PDF);
});

it("never puts a file opened under one account in the next account's composer", async () => {
  const screen = await render(<OpenedDocumentBootstrap />);
  copy.mockImplementation(async () => {
    // Signed out, and another account signed in, while the file was being copied.
    signIn(3);
    return PDF;
  });
  await open();
  await screen.rerender(<OpenedDocumentBootstrap />);
  await settle();
  expect(takeQueuedComposerAttachment("new")).toBeNull();
  expect(startNewChatGlobal).not.toHaveBeenCalled();
});

it("says why a file cannot be attached, and moves nothing", async () => {
  copy.mockRejectedValue(new AttachmentError("too_large"));
  mockParams = { chatId: "chat-1" };
  await render(<OpenedDocumentBootstrap />);
  await open();
  expect(mockError).toHaveBeenCalledWith("chat.opened_file_too_large");
  expect(takeQueuedComposerAttachment("new")).toBeNull();
  expect(startNewChatGlobal).not.toHaveBeenCalled();
});

it("watches Android's Open with and Share for as long as the app runs", async () => {
  const screen = await render(<OpenedDocumentBootstrap />);
  expect(watchAndroidOpenedDocuments).toHaveBeenCalledTimes(1);
  await screen.unmount();
  expect(mockStopWatching).toHaveBeenCalled();
});

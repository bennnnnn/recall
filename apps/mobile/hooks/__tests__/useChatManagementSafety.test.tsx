import React from "react";
import { Alert, Text } from "react-native";
import { act, render } from "@testing-library/react-native";

import { useChatActions } from "@/hooks/useChatActions";
import { api, type Chat } from "@/lib/api";
import { getCachedChat } from "@/lib/cache/chatListCache";
import { abandonActiveChatIfDeleted, insertChatGlobal, moveChatArchiveGlobal, patchChatGlobal } from "@/lib/drawer";
import { clearCachedChatMessages } from "@/lib/chatMessageCache";

let mockSession = 0;
const mockError = jest.fn();
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => ({ error: mockError }) }));
jest.mock("@/lib/cache/chatListCache", () => ({ getCachedChat: jest.fn(), peekCreatedChat: jest.fn() }));
jest.mock("@/lib/api", () => ({ api: { getChat: jest.fn(), renameChat: jest.fn(), setPin: jest.fn(), setArchive: jest.fn(), deleteChat: jest.fn() } }));
jest.mock("@/lib/drawer", () => ({
  insertChatGlobal: jest.fn(), moveChatArchiveGlobal: jest.fn(), patchChatGlobal: jest.fn(),
  removeChatGlobal: jest.fn(), abandonActiveChatIfDeleted: jest.fn(),
}));
jest.mock("@/lib/chatMessageCache", () => ({ clearCachedChatMessages: jest.fn() }));
jest.mock("@/lib/cache/galleryListCache", () => ({ invalidateGalleryCache: jest.fn() }));
jest.mock("@/lib/exportMessagePdf", () => ({ exportConversationAsPdf: jest.fn() }));
jest.mock("@/lib/exportPdf", () => ({ isShareCancelled: jest.fn() }));
jest.mock("@/lib/share", () => ({ shareConversation: jest.fn() }));
jest.mock("@/lib/haptics", () => ({ tap: jest.fn() }));

const setChatTitle = jest.fn();
const setPinned = jest.fn();
const setArchived = jest.fn();
const router = { canGoBack: () => true, back: jest.fn(), replace: jest.fn() };
let actions: ReturnType<typeof useChatActions>;
function Probe({ chatId = "chat-1", token = "token" }: { chatId?: string; token?: string }) {
  const value = useChatActions({
    token, chatId, chatTitle: "Old title", messages: [], pinned: false, archived: false,
    setPinned, setArchived, setChatTitle, setMessages: jest.fn(), router: router as never, t: (key) => key,
  });
  React.useLayoutEffect(() => { actions = value; });
  return <Text>Actions</Text>;
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function deletePress() {
  const buttons = (Alert.alert as jest.Mock).mock.calls.at(-1)?.[2] as { style?: string; onPress?: () => Promise<void> }[];
  return buttons.find((button) => button.style === "destructive")!.onPress!;
}
beforeEach(() => {
  jest.clearAllMocks(); mockSession = 0;
  jest.mocked(getCachedChat).mockReturnValue(undefined);
  jest.spyOn(Alert, "alert").mockImplementation(() => {});
});

describe.each([
  ["rename", "renameChat", "confirmRename", setChatTitle],
  ["pin", "setPin", "togglePin", setPinned],
  ["archive", "setArchive", "toggleArchive", setArchived],
] as const)("%s lifetime", (_name, apiMethod, action, setter) => {
  it.each(["resolve", "reject"] as const)("does not update a different chat when its request %ss", async (outcome) => {
    const request = deferred<{ title: string }>();
    (api[apiMethod] as jest.Mock).mockReturnValue(request.promise);
    const view = await render(<Probe />);
    await act(async () => { actions.setRenameText("New title"); });
    let pending!: Promise<void>;
    await act(async () => { pending = actions[action](); });
    await view.rerender(<Probe chatId="chat-2" />);
    setter.mockClear();
    await act(async () => {
      if (outcome === "resolve") request.resolve({ title: "Saved" });
      else request.reject(new Error("offline"));
      await pending;
    });
    expect(setter).not.toHaveBeenCalled();
    expect(mockError).not.toHaveBeenCalled();
    expect(actions.actionBanner).toBeNull();
  });
});

it("does not reconcile an old account's rename into the next account", async () => {
  const request = deferred<{ title: string }>();
  (api.renameChat as jest.Mock).mockReturnValue(request.promise);
  const view = await render(<Probe />);
  await act(async () => { actions.setRenameText("New title"); });
  let pending!: Promise<void>;
  await act(async () => { pending = actions.confirmRename(); });
  mockSession++;
  await view.rerender(<Probe token="account-2" />);
  jest.mocked(patchChatGlobal).mockClear(); setChatTitle.mockClear();
  await act(async () => { request.resolve({ title: "Old account" }); await pending; });
  expect(setChatTitle).not.toHaveBeenCalled();
  expect(patchChatGlobal).not.toHaveBeenCalled();
  expect(actions.actionBanner).toBeNull();
});

it("updates the drawer pin immediately and rolls it back on failure", async () => {
  (api.setPin as jest.Mock).mockRejectedValue(new Error("offline"));
  await render(<Probe />);
  await act(async () => { await actions.togglePin(); });
  expect(patchChatGlobal).toHaveBeenNthCalledWith(1, "chat-1", { pinned: true });
  expect(patchChatGlobal).toHaveBeenNthCalledWith(2, "chat-1", { pinned: false });
});

it("ignores a retained delete confirmation after navigating to another chat", async () => {
  const view = await render(<Probe />);
  await act(async () => { actions.confirmDelete(); });
  const confirm = deletePress();
  await view.rerender(<Probe chatId="chat-2" />);
  await act(async () => { await confirm(); });
  expect(api.deleteChat).not.toHaveBeenCalled();
});

it("ignores a retained delete confirmation immediately after account invalidation", async () => {
  await render(<Probe />);
  await act(async () => { actions.confirmDelete(); });
  const confirm = deletePress();
  mockSession++;
  await act(async () => { await confirm(); });
  expect(api.deleteChat).not.toHaveBeenCalled();
});

it("clears the active deleted conversation through the registered new-chat action", async () => {
  (api.deleteChat as jest.Mock).mockResolvedValue(undefined);
  await render(<Probe />);
  await act(async () => { actions.confirmDelete(); });
  await act(async () => { await deletePress()(); });
  expect(clearCachedChatMessages).toHaveBeenCalledWith("chat-1");
  expect(abandonActiveChatIfDeleted).toHaveBeenCalledWith(["chat-1"]);
  expect(router.back).not.toHaveBeenCalled();
  expect(router.replace).not.toHaveBeenCalled();
});

it("coalesces repeated archive taps while the mutation is pending, including token refresh", async () => {
  const request = deferred<{ title: string }>();
  (api.setArchive as jest.Mock).mockReturnValue(request.promise);
  const view = await render(<Probe />);
  let pending!: Promise<void>;
  await act(async () => { pending = actions.toggleArchive(); });
  await view.rerender(<Probe token="refreshed-token" />);
  await act(async () => { void actions.toggleArchive(); });
  expect(api.setArchive).toHaveBeenCalledTimes(1);
  await act(async () => { request.resolve({ title: "Saved" }); await pending; });
  expect(actions.actionBanner?.message).toBe("chat.archived_toast");
  expect(moveChatArchiveGlobal).toHaveBeenCalledWith("chat-1", true);
});

it("closes a rename editor when its conversation changes", async () => {
  const view = await render(<Probe />);
  await act(async () => { actions.openRename(); actions.setRenameText("Unsaved old title"); });
  await view.rerender(<Probe chatId="chat-2" />);
  expect(actions.renameVisible).toBe(false);
  expect(actions.renameText).toBe("");
});

it("restores the original dated project chat after a failed delete", async () => {
  const original = { id: "chat-1", title: "Old project", model: "free-chat", pinned: true,
    archived: false, created_at: "2025-01-01", updated_at: "2025-02-01", project_id: "project", quiz_mode: "exam" } as Chat;
  jest.mocked(getCachedChat).mockReturnValue(original);
  (api.deleteChat as jest.Mock).mockRejectedValue(new Error("offline"));
  await render(<Probe />);
  await act(async () => { actions.confirmDelete(); });
  await act(async () => { await deletePress()(); });
  expect(insertChatGlobal).toHaveBeenCalledWith(original);
  expect(api.getChat).not.toHaveBeenCalled();
});

it("recovers real metadata after a failed delete when the chat was outside the cached list", async () => {
  const original = { id: "chat-1", title: "Older than list", updated_at: "2025-02-01", project_id: "project" } as Chat;
  (api.deleteChat as jest.Mock).mockRejectedValue(new Error("offline"));
  (api.getChat as jest.Mock).mockResolvedValue(original);
  await render(<Probe />);
  await act(async () => { actions.confirmDelete(); });
  await act(async () => { await deletePress()(); });
  expect(api.getChat).toHaveBeenCalledWith("token", "chat-1");
  expect(insertChatGlobal).toHaveBeenCalledWith(original);
  expect(mockError).toHaveBeenCalledWith("chat.delete_failed");
});

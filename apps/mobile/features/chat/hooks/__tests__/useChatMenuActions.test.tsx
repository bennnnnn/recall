import React from "react";
import { Alert, Text } from "react-native";
import { act, render } from "@testing-library/react-native";
import { useChatMenuActions } from "@/features/chat/hooks/useChatMenuActions";
import { api, type Chat } from "@/lib/api";
import { ApiRequestError } from "@/lib/api/errorBody";
import { beginChatMutation } from "@/features/chat/model/mutationLock";

let mockSession = 0;
const mockError = jest.fn();
const mockDestructive = jest.fn();
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => ({ error: mockError }) }));
jest.mock("@/lib/api", () => ({ api: { renameChat: jest.fn(), setPin: jest.fn(), setArchive: jest.fn(), deleteChat: jest.fn(), listAllMessages: jest.fn() } }));
jest.mock("@/features/chat/model/messageCache", () => ({ clearCachedChatMessages: jest.fn() }));
jest.mock("@/features/chat/model/chatListCache", () => ({ getCachedChat: () => undefined, peekCreatedChat: () => undefined }));
jest.mock("@/features/chat/model/exportPdf", () => ({ printHtmlToSharedPdf: jest.fn() }));
const mockShare = jest.fn(async (_options: { message: string; title?: string | null }) => {});
jest.mock("@/lib/share", () => ({ presentShareSheet: (options: { message: string; title?: string | null }) => mockShare(options) }));
const mockPdf = jest.fn(async (_title: string | null, _messages: unknown[], _onSharing?: () => void) => {});
jest.mock("@/features/chat/model/exportMessagePdf", () => ({
  exportConversationAsPdf: (title: string | null, messages: unknown[], onSharing?: () => void) => mockPdf(title, messages, onSharing),
}));
jest.mock("@/features/chat/drawer/drawer", () => ({ abandonActiveChatIfDeleted: jest.fn() }));
jest.mock("@/lib/haptics", () => ({
  ...jest.requireActual("@/lib/haptics"),
  notifyDestructive: (...args: unknown[]) => mockDestructive(...args),
}));
const chat: Chat = { id: "one", title: "Original", model: "free-chat", pinned: true, archived: false, created_at: "2026-01-01", updated_at: "2026-01-01" };
const patch = jest.fn();
const remove = jest.fn();
const insert = jest.fn();
let current: ReturnType<typeof useChatMenuActions>;
function Probe({ token = "token", open = true }: { token?: string; open?: boolean }) {
  const result = useChatMenuActions({ token, isDrawerOpen: open, patchChatInGroups: patch, insertChatInGroups: insert, removeChatFromGroupsById: remove });
  React.useLayoutEffect(() => { current = result; });
  return <Text>menu</Text>;
}
beforeEach(() => { jest.clearAllMocks(); mockSession++; jest.spyOn(Alert, "alert").mockImplementation(() => {}); });

it("restores a pinned chat when optimistic archive fails", async () => {
  (api.setArchive as jest.Mock).mockRejectedValueOnce(new Error("offline"));
  await render(<Probe />);
  await act(async () => { current.showRowMenu(chat); });
  await act(async () => { await current.toggleArchiveChat(); });
  expect(patch).toHaveBeenCalledWith("one", { archived: true, pinned: false });
  expect(patch).toHaveBeenLastCalledWith("one", { archived: false, pinned: true });
  expect(mockError).toHaveBeenCalledWith("chat.archive_failed");
});

it.each([
  ["at the pin limit", new ApiRequestError(409, JSON.stringify({ detail: { code: "pin_limit", message: "full", limit: 50 } })), "chat.pin_limit"],
  ["offline", new Error("offline"), "chat.pin_failed"],
])("unpins again and says why when a pin fails %s", async (_case, error, message) => {
  (api.setPin as jest.Mock).mockRejectedValueOnce(error);
  await render(<Probe />);
  await act(async () => { current.showRowMenu({ ...chat, pinned: false }); });
  await act(async () => { await current.togglePinChat(); });
  expect(patch).toHaveBeenLastCalledWith("one", { pinned: false });
  expect(mockError).toHaveBeenCalledWith(message);
});

it("ignores failed rename completion after account switch", async () => {
  let fail!: (error: Error) => void;
  (api.renameChat as jest.Mock).mockReturnValueOnce(new Promise((_resolve, reject) => { fail = reject; }));
  const view = await render(<Probe />);
  await act(async () => { current.showRowMenu(chat); });
  await act(async () => { current.openRenameFromMenu(); });
  await act(async () => { current.setRenameText("Changed"); });
  let request!: Promise<void>;
  await act(async () => { request = current.confirmRename(); });
  mockSession++;
  await view.rerender(<Probe token="new-account" />);
  await act(async () => { fail(new Error("old account")); await request; });
  expect(patch).toHaveBeenCalledTimes(1);
  expect(patch).toHaveBeenCalledWith("one", { title: "Changed" });
  expect(mockError).not.toHaveBeenCalled();
  expect(current.renameVisible).toBe(false);
});

it("shares the long-pressed chat as text straight through the OS share menu", async () => {
  // The user wants the share sheet with contacts and apps, not one of Recall's first (2026-11-07).
  (api.listAllMessages as jest.Mock).mockResolvedValueOnce([]);
  await render(<Probe />);
  await act(async () => { current.showRowMenu(chat); });
  await act(async () => { current.openShareChat(); });
  expect(current.menuChat).toBeNull();
  expect(api.listAllMessages).toHaveBeenCalledWith("token", "one");
  expect(mockShare).toHaveBeenCalledTimes(1);
  expect(mockShare.mock.calls[0][0]).toMatchObject({ title: "Original" });
  expect(mockShare.mock.calls[0][0].message).toMatch(/^Original\n\n/);
});

it("exports the long-pressed chat as a PDF", async () => {
  const messages = [{ content: "hello" }];
  (api.listAllMessages as jest.Mock).mockResolvedValueOnce(messages);
  await render(<Probe />);
  await act(async () => { current.showRowMenu(chat); });
  await act(async () => { current.exportChatPdf(); });
  expect(current.menuChat).toBeNull();
  expect(mockPdf).toHaveBeenCalledWith("Original", messages, expect.any(Function));
});

it.each([
  ["the drawer closes", (view: Awaited<ReturnType<typeof render>>) => view.rerender(<Probe open={false} />)],
  ["the account switches", (view: Awaited<ReturnType<typeof render>>) => { mockSession++; return view.rerender(<Probe token="b" />); }],
])("does not share private history read before %s", async (_case, change) => {
  let finish!: (messages: unknown[]) => void;
  (api.listAllMessages as jest.Mock).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const view = await render(<Probe />);
  await act(async () => { current.showRowMenu(chat); });
  await act(async () => { current.openShareChat(); });
  await change(view);
  await act(async () => { finish([{ content: "private" }]); });
  expect(mockShare).not.toHaveBeenCalled();
  expect(mockError).not.toHaveBeenCalled();
});

it("rejects a delete confirmation retained after account switch", async () => {
  const view = await render(<Probe />);
  await act(async () => { current.showRowMenu(chat); });
  await act(async () => { current.confirmDeleteChat(); });
  const buttons = (Alert.alert as jest.Mock).mock.calls[0][2];
  const confirm = buttons.find((button: { style: string }) => button.style === "destructive").onPress;
  mockSession++;
  await view.rerender(<Probe token="b" />);
  await act(async () => { await confirm(); });
  expect(api.deleteChat).not.toHaveBeenCalled();
  expect(remove).not.toHaveBeenCalled();
});

it("does not submit a second surface's mutation for a busy chat", async () => {
  await render(<Probe />);
  await act(async () => { current.showRowMenu(chat); });
  const release = beginChatMutation(mockSession, [chat.id]);
  await act(async () => { await current.toggleArchiveChat(); });
  expect(api.setArchive).not.toHaveBeenCalled();
  expect(patch).not.toHaveBeenCalled();
  release?.();
});

it("keeps a rename editor open when its title is invalid", async () => {
  await render(<Probe />);
  await act(async () => { current.showRowMenu(chat); });
  await act(async () => { current.openRenameFromMenu(); });
  await act(async () => { current.setRenameText("   "); });
  await act(async () => { await current.confirmRename(); });
  expect(current.renameVisible).toBe(true);
  expect(api.renameChat).not.toHaveBeenCalled();
  expect(mockError).toHaveBeenCalledWith("chat.rename_blank");
});

it("reaffirms successful deletion after a concurrent list read", async () => {
  (api.deleteChat as jest.Mock).mockResolvedValueOnce(undefined);
  await render(<Probe />);
  await act(async () => { current.showRowMenu(chat); });
  await act(async () => { current.confirmDeleteChat(); });
  const buttons = (Alert.alert as jest.Mock).mock.calls[0][2];
  const confirm = buttons.find((button: { style: string }) => button.style === "destructive").onPress;
  await act(async () => { await confirm(); });
  expect(remove).toHaveBeenCalledTimes(2);
  expect(insert).not.toHaveBeenCalled();
  expect(mockDestructive).toHaveBeenCalledTimes(1);
});

it.each(["pin", "archive"])("uses the returned state for the drawer %s confirmation", async (kind) => {
  (api.setPin as jest.Mock).mockResolvedValueOnce(chat);
  (api.setArchive as jest.Mock).mockResolvedValueOnce(chat);
  await render(<Probe />);
  await act(async () => { current.showRowMenu(chat); });
  await act(async () => {
    if (kind === "pin") await current.togglePinChat();
    else await current.toggleArchiveChat();
  });
  expect(current.actionBanner).toEqual(kind === "pin"
    ? { message: "chat.pinned_toast", icon: "pin" }
    : { message: "chat.unarchived_toast", icon: "unarchive" });
});

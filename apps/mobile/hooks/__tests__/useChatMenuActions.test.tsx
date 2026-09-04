import React from "react";
import { Alert, Text } from "react-native";
import { act, render } from "@testing-library/react-native";
import { useChatMenuActions } from "@/hooks/useChatMenuActions";
import { api, type Chat } from "@/lib/api";
import { shareConversation } from "@/lib/share";
import { beginChatMutation } from "@/lib/chat/chatMutationLock";

let mockSession = 0;
const mockError = jest.fn();
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => ({ error: mockError }) }));
jest.mock("react-i18next", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
jest.mock("@/lib/api", () => ({ api: { renameChat: jest.fn(), setPin: jest.fn(), setArchive: jest.fn(), deleteChat: jest.fn(), listAllMessages: jest.fn() } }));
jest.mock("@/lib/chatMessageCache", () => ({ clearCachedChatMessages: jest.fn() }));
jest.mock("@/lib/cache/chatListCache", () => ({ getCachedChat: () => undefined }));
jest.mock("@/lib/cache/galleryListCache", () => ({ invalidateGalleryCache: jest.fn() }));
jest.mock("@/lib/exportPdf", () => ({ isShareCancelled: () => false }));
jest.mock("@/lib/share", () => ({ shareConversation: jest.fn() }));
jest.mock("@/lib/drawer", () => ({ abandonActiveChatIfDeleted: jest.fn() }));
const chat: Chat = { id: "one", title: "Original", model: "free-chat", pinned: true, archived: false, created_at: "2026-01-01", updated_at: "2026-01-01" };
const patch = jest.fn();
const moveArchive = jest.fn();
const remove = jest.fn();
const insert = jest.fn();
const movePin = jest.fn();
let current: ReturnType<typeof useChatMenuActions>;
function Probe({ token = "token", open = true }: { token?: string; open?: boolean }) {
  const result = useChatMenuActions({ token, isDrawerOpen: open, patchChatInGroups: patch, insertChatInGroups: insert, moveChatPinState: movePin, moveChatArchiveState: moveArchive, removeChatFromGroupsById: remove });
  React.useLayoutEffect(() => { current = result; });
  return <Text>menu</Text>;
}
beforeEach(() => { jest.clearAllMocks(); mockSession++; jest.spyOn(Alert, "alert").mockImplementation(() => {}); });

it("restores a pinned chat when optimistic archive fails", async () => {
  (api.setArchive as jest.Mock).mockRejectedValueOnce(new Error("offline"));
  await render(<Probe />);
  await act(async () => { current.showRowMenu(chat); });
  await act(async () => { await current.toggleArchiveChat(); });
  expect(moveArchive).toHaveBeenCalledWith("one", true);
  expect(patch).toHaveBeenCalledWith("one", { archived: false, pinned: true });
  expect(mockError).toHaveBeenCalledWith("common.error");
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

it("does not share fetched private history after drawer dismissal", async () => {
  let finish!: (messages: unknown[]) => void;
  (api.listAllMessages as jest.Mock).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const view = await render(<Probe />);
  await act(async () => { current.showRowMenu(chat); });
  let request!: Promise<void>;
  await act(async () => { request = current.handleShareChat(); });
  await view.rerender(<Probe open={false} />);
  await act(async () => { finish([{ content: "private" }]); await request; });
  expect(shareConversation).not.toHaveBeenCalled();
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
  expect(moveArchive).not.toHaveBeenCalled();
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
});

import React from "react";
import { Alert, Text } from "react-native";
import { act, render } from "@testing-library/react-native";
import { useChatBulkActions } from "@/hooks/useChatBulkActions";
import { api, type Chat } from "@/lib/api";
import { abandonActiveChatIfDeleted } from "@/lib/drawer";
import { clearCachedChatMessages } from "@/lib/chatMessageCache";
import { getCachedChat } from "@/lib/cache/chatListCache";
import { invalidateGalleryCache } from "@/lib/cache/galleryListCache";

let mockSession = 0;
const mockError = jest.fn();
const mockT = jest.fn((key: string, _options?: Record<string, unknown>) => key);
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));
jest.mock("react-i18next", () => ({ useTranslation: () => ({ t: mockT }) }));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => ({ error: mockError }) }));
jest.mock("@/lib/api", () => ({ api: { setArchive: jest.fn(), deleteChat: jest.fn() } }));
jest.mock("@/lib/drawer", () => ({ abandonActiveChatIfDeleted: jest.fn() }));
jest.mock("@/lib/chatMessageCache", () => ({ clearCachedChatMessages: jest.fn() }));
jest.mock("@/lib/cache/chatListCache", () => ({ getCachedChat: jest.fn() }));
jest.mock("@/lib/cache/galleryListCache", () => ({ invalidateGalleryCache: jest.fn() }));
const first: Chat = {
  id: "first", title: "First", pinned: true, archived: false, model: "free-chat",
  created_at: "2026-01-01", updated_at: "2026-01-01",
};
const second: Chat = { ...first, id: "second", title: "Second", pinned: false };
const insertChatInGroups = jest.fn();
const patchChatInGroups = jest.fn();
const moveChatArchiveState = jest.fn();
const removeChatFromGroupsById = jest.fn();
const reloadChats = jest.fn();
const showActionBanner = jest.fn();
let actions: ReturnType<typeof useChatBulkActions>;
function Probe({ token = "token", isDrawerOpen = true }: { token?: string; isDrawerOpen?: boolean }) {
  const value = useChatBulkActions({ token, isDrawerOpen, insertChatInGroups, patchChatInGroups, moveChatArchiveState,
    removeChatFromGroupsById, reloadChats, showActionBanner });
  React.useLayoutEffect(() => { actions = value; });
  return <Text>Bulk actions</Text>;
}
function confirmation() {
  const buttons = (Alert.alert as jest.Mock).mock.calls.at(-1)?.[2] as { onPress?: () => Promise<void> }[];
  return buttons.find((button) => button.onPress)!.onPress!;
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
beforeEach(() => {
  jest.clearAllMocks(); mockSession = 0;
  jest.mocked(getCachedChat).mockReturnValue(undefined);
  jest.spyOn(Alert, "alert").mockImplementation(() => {});
});

it("keeps successful deletes removed, clears their cache and abandons only deleted active chats on partial failure", async () => {
  (api.deleteChat as jest.Mock).mockImplementation((_token: string, id: string) =>
    id === first.id ? Promise.resolve() : Promise.reject(new Error("offline")));
  await render(<Probe />);
  const complete = jest.fn();
  await act(async () => { actions.bulkDeleteChats([first, second], complete); });
  await act(async () => { await confirmation()(); });
  expect(insertChatInGroups).toHaveBeenCalledTimes(1);
  expect(insertChatInGroups).toHaveBeenCalledWith(second);
  expect(clearCachedChatMessages).toHaveBeenCalledWith(first.id);
  expect(clearCachedChatMessages).not.toHaveBeenCalledWith(second.id);
  expect(invalidateGalleryCache).toHaveBeenCalledTimes(1);
  expect(abandonActiveChatIfDeleted).toHaveBeenCalledWith([first.id]);
  expect(complete).not.toHaveBeenCalled();
  expect(mockError).toHaveBeenCalledWith("chat.delete_failed");
});

it("waits for all archive results and restores only failed snapshots, including their pins", async () => {
  const request = deferred<Chat>();
  (api.setArchive as jest.Mock).mockImplementation((_token: string, id: string) =>
    id === first.id ? Promise.reject(new Error("offline")) : request.promise);
  await render(<Probe />);
  await act(async () => { actions.bulkArchiveChats([first, second]); });
  let pending!: Promise<void>;
  await act(async () => { pending = confirmation()(); });
  expect(reloadChats).not.toHaveBeenCalled();
  expect(insertChatInGroups).not.toHaveBeenCalled();
  await act(async () => { request.resolve({ ...second, archived: true }); await pending; });
  expect(patchChatInGroups).toHaveBeenCalledTimes(2);
  expect(patchChatInGroups).toHaveBeenCalledWith(first.id, first);
  expect(patchChatInGroups).toHaveBeenCalledWith(second.id, { pinned: false, archived: true });
  expect(moveChatArchiveState).not.toHaveBeenCalledWith(second.id, false);
  expect(mockError).toHaveBeenCalledWith("chat.archive_failed");
});

it.each(["bulkArchiveChats", "bulkDeleteChats"] as const)("ignores %s confirmation after drawer closes", async (method) => {
  const view = await render(<Probe />);
  await act(async () => { actions[method]([first]); });
  const confirm = confirmation();
  await view.rerender(<Probe isDrawerOpen={false} />);
  await act(async () => { await confirm(); });
  expect(api.setArchive).not.toHaveBeenCalled();
  expect(api.deleteChat).not.toHaveBeenCalled();
});

it("ignores an old batch's result after account invalidation before a rerender", async () => {
  const request = deferred<void>();
  (api.deleteChat as jest.Mock).mockReturnValue(request.promise);
  await render(<Probe />);
  await act(async () => { actions.bulkDeleteChats([first]); });
  let pending!: Promise<void>;
  await act(async () => { pending = confirmation()(); });
  mockSession++;
  await act(async () => { request.resolve(); await pending; });
  expect(clearCachedChatMessages).not.toHaveBeenCalled();
  expect(abandonActiveChatIfDeleted).not.toHaveBeenCalled();
  expect(showActionBanner).not.toHaveBeenCalled();
});

it("does not apply an old batch's success callback to a reopened drawer", async () => {
  const request = deferred<void>();
  (api.deleteChat as jest.Mock).mockReturnValue(request.promise);
  const view = await render(<Probe />);
  const complete = jest.fn();
  await act(async () => { actions.bulkDeleteChats([first], complete); });
  let pending!: Promise<void>;
  await act(async () => { pending = confirmation()(); });
  await view.rerender(<Probe isDrawerOpen={false} />);
  await view.rerender(<Probe />);
  await act(async () => { request.resolve(); await pending; });
  expect(clearCachedChatMessages).toHaveBeenCalledWith(first.id);
  expect(complete).not.toHaveBeenCalled();
  expect(showActionBanner).not.toHaveBeenCalled();
});

it("uses the latest row at confirmation when restoring a failed archive", async () => {
  const latest = { ...first, title: "Renamed before confirmation", pinned: false };
  (api.setArchive as jest.Mock).mockRejectedValue(new Error("offline"));
  await render(<Probe />);
  await act(async () => { actions.bulkArchiveChats([first]); });
  jest.mocked(getCachedChat).mockReturnValue(latest);
  await act(async () => { await confirmation()(); });
  expect(patchChatInGroups).toHaveBeenCalledWith(first.id, latest);
});

it("reconciles each fulfilled archive with its returned flags and reports the actual archived count", async () => {
  const savedFirst = { ...first, pinned: true, archived: false };
  const savedSecond = { ...second, pinned: false, archived: true };
  jest.mocked(api.setArchive).mockImplementation(async (_token, id) => id === first.id ? savedFirst : savedSecond);
  const complete = jest.fn();
  await render(<Probe />);
  await act(async () => { actions.bulkArchiveChats([first, second], complete); });
  await act(async () => { await confirmation()(); });
  expect(patchChatInGroups).toHaveBeenCalledWith(first.id, { pinned: true, archived: false });
  expect(patchChatInGroups).toHaveBeenCalledWith(second.id, { pinned: false, archived: true });
  expect(mockT).toHaveBeenCalledWith("drawer.bulk_archived_toast", { count: 1 });
  expect(complete).toHaveBeenCalledTimes(1);
  expect(mockError).not.toHaveBeenCalled();
});

it("does not report chats archived when all returned rows are active again", async () => {
  jest.mocked(api.setArchive).mockResolvedValue(first);
  const complete = jest.fn();
  await render(<Probe />);
  await act(async () => { actions.bulkArchiveChats([first], complete); });
  await act(async () => { await confirmation()(); });
  expect(patchChatInGroups).toHaveBeenCalledWith(first.id, { pinned: true, archived: false });
  expect(showActionBanner).not.toHaveBeenCalled();
  expect(complete).toHaveBeenCalledTimes(1);
});

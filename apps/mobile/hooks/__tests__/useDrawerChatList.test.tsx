import React from "react";
import { Text } from "react-native";
import { act, render } from "@testing-library/react-native";
import { useDrawerChatList } from "@/hooks/useDrawerChatList";
import { api, type ChatList } from "@/lib/api";
import { getCachedChatList, invalidateChatListCache, setChatListCache } from "@/lib/cache/chatListCache";
import { emptyChatList } from "@/lib/chat/chatListSections";
import { patchChatGlobal, subscribeChatChanges } from "@/lib/drawer";

let mockSession = 0;
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession, requireTokenSession: jest.fn() }));
jest.mock("@/lib/api", () => ({ api: { listChats: jest.fn() } }));
jest.mock("@/lib/scheduleIdle", () => ({ scheduleIdleTask: () => jest.fn() }));
const chat = { id: "old", title: "Original", model: "free-chat", pinned: false, updated_at: "2026-01-01T00:00:00Z", created_at: "2026-01-01T00:00:00Z" };
const initial = { ...emptyChatList(), older: [chat] };
let current: ReturnType<typeof useDrawerChatList>;
function Probe({ token = "token", open = true }: { token?: string | null; open?: boolean }) {
  const result = useDrawerChatList({ token, isDrawerOpen: open });
  React.useLayoutEffect(() => { current = result; });
  return <Text>{result.allChats.map((row) => row.title).join(",")}</Text>;
}
beforeEach(() => {
  jest.clearAllMocks(); mockSession = 0; invalidateChatListCache();
});

it("hides account A immediately and rejects its late read after account B signs in", async () => {
  let finish!: (value: ChatList) => void;
  (api.listChats as jest.Mock).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const view = await render(<Probe />);
  mockSession++;
  (api.listChats as jest.Mock).mockResolvedValueOnce({ ...emptyChatList(), today: [{ ...chat, id: "b", title: "Account B" }] });
  await view.rerender(<Probe token="b-token" />);
  expect(current.allChats.map((row) => row.id)).toEqual(["b"]);
  await act(async () => { finish(initial); });
  expect(current.allChats.map((row) => row.id)).toEqual(["b"]);
  expect(current.error).toBe(false);
});

it("retains loaded rows through access-token refresh without another list request", async () => {
  setChatListCache(initial);
  const view = await render(<Probe />);
  await view.rerender(<Probe token="rotated-token" />);
  expect(current.allChats).toEqual([chat]);
  expect(api.listChats).not.toHaveBeenCalled();
});

it("reconciles pin/rename edits over a stale refresh and broadcasts the same metadata", async () => {
  setChatListCache(initial);
  await render(<Probe />);
  let finish!: (value: ChatList) => void;
  (api.listChats as jest.Mock).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const changed = jest.fn();
  const unsubscribe = subscribeChatChanges(changed);
  let read!: Promise<void>;
  await act(async () => { read = current.handleRefresh(); });
  await act(async () => { patchChatGlobal(chat.id, { pinned: true, title: "Renamed" }); });
  await act(async () => { finish(initial); await read; });
  expect(current.groups.pinned[0]).toMatchObject({ id: "old", title: "Renamed", pinned: true });
  expect(current.groups.older).toEqual([]);
  expect(getCachedChatList()).toEqual(current.groups);
  expect(changed).toHaveBeenCalledWith(chat.id, { pinned: true, title: "Renamed" });
  unsubscribe();
});

it("preserves visible history and allows retry after a failed refresh", async () => {
  setChatListCache(initial);
  await render(<Probe />);
  (api.listChats as jest.Mock).mockRejectedValueOnce(new Error("offline"));
  await act(async () => { await current.handleRefresh(); });
  expect(current.allChats).toEqual([chat]);
  expect(current.error).toBe(true);
  expect(current.refreshing).toBe(false);
  (api.listChats as jest.Mock).mockResolvedValueOnce(initial);
  await act(async () => { await current.handleRefresh(); });
  expect(current.error).toBe(false);
});


it("does not paint a resolved response over an edit queued before the hook resumes", async () => {
  setChatListCache(initial);
  await render(<Probe />);
  let finish!: (value: ChatList) => void;
  (api.listChats as jest.Mock).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  let read!: Promise<void>;
  await act(async () => { read = current.handleRefresh(); });
  await act(async () => {
    finish(initial);
    await Promise.resolve();
    patchChatGlobal(chat.id, { title: "Newest edit" });
    await read;
  });
  expect(current.allChats[0].title).toBe("Newest edit");
  expect(getCachedChatList()).toEqual(current.groups);
});

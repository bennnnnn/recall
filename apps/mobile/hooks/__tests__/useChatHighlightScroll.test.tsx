import React from "react";
import { Text } from "react-native";
import { act, render } from "@testing-library/react-native";
import { useChatHighlightScroll } from "@/hooks/useChatHighlightScroll";
import type { Message } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { clearChatHighlightGlobal } from "@/lib/drawer";

jest.mock("@/lib/auth", () => ({ getSessionGeneration: jest.fn(() => 0) }));
const scroll = jest.fn();
const load = jest.fn(async () => {});
const router = { setParams: jest.fn() };
const listRef = { current: { scrollToIndex: scroll } };
const message = (id: string): Message => ({ id, role: "user", content: id, model: null, created_at: "2026-01-01" });
const initial = [message("latest")];
let highlight: string | null;
function Probe({ routeId = "chat-a", chatId = routeId, target, messages = initial, more = false, loading = false, chatLoading = false }: {
  routeId?: string; chatId?: string; target?: string; messages?: Message[]; more?: boolean; loading?: boolean; chatLoading?: boolean;
}) {
  const result = useChatHighlightScroll({
    routeChatId: routeId, chatId, routeHighlightMessage: target, messages,
    hasMoreOlder: more, chatLoading, loadingOlder: loading, token: "token", loadOlderMessages: load,
    router: router as never, listRef: listRef as never,
  });
  React.useLayoutEffect(() => { highlight = result.highlightedMessageId; });
  return <Text>{result.highlightedMessageId ?? "none"}</Text>;
}
const frames = new Map<number, (time: number) => void>();
let nextFrame = 0;
async function flushFrames() {
  await act(async () => {
    const callbacks = [...frames.values()]; frames.clear(); callbacks.forEach((fn) => fn(0));
  });
}
beforeEach(() => {
  jest.useFakeTimers(); jest.clearAllMocks(); frames.clear(); (getSessionGeneration as jest.Mock).mockReturnValue(0);
  jest.spyOn(global, "requestAnimationFrame").mockImplementation((fn) => { frames.set(++nextFrame, fn); return nextFrame; });
  jest.spyOn(global, "cancelAnimationFrame").mockImplementation((id) => { frames.delete(id); });
});
afterEach(() => { jest.restoreAllMocks(); jest.useRealTimers(); });

it.each(["navigate", "logout", "unmount"])("drops a queued search-result scroll after %s", async (change) => {
  const view = await render(<Probe target="latest" />);
  if (change === "navigate") await view.rerender(<Probe routeId="chat-b" />);
  if (change === "logout") (getSessionGeneration as jest.Mock).mockReturnValue(1);
  if (change === "unmount") await view.unmount();
  await flushFrames();
  expect(scroll).not.toHaveBeenCalled();
});

it("does not page a different conversation for an old search hit", async () => {
  const view = await render(<Probe target="old-a" />);
  await view.rerender(<Probe routeId="chat-b" more />);
  expect(load).not.toHaveBeenCalled();
  expect(highlight).toBeNull();
});

it("does not let an older highlight timeout clear the next search hit", async () => {
  const view = await render(<Probe target="latest" />);
  await flushFrames();
  await act(async () => { jest.advanceTimersByTime(2000); });
  await view.rerender(<Probe routeId="chat-b" target="match-b" messages={[message("match-b")]} />);
  await flushFrames();
  await act(async () => { jest.advanceTimersByTime(1500); });
  expect(highlight).toBe("match-b");
  await act(async () => { jest.advanceTimersByTime(2000); });
  expect(highlight).toBeNull();
});

it("does not automatically retry the same failed history page", async () => {
  const view = await render(<Probe target="old-a" more />);
  expect(load).toHaveBeenCalledTimes(1);
  await view.rerender(<Probe target="old-a" more loading />);
  await view.rerender(<Probe target="old-a" more />);
  expect(load).toHaveBeenCalledTimes(1);
});

it("waits for the destination conversation before paging a search hit", async () => {
  const view = await render(<Probe routeId="chat-b" chatId="chat-a" target="old-b" more />);
  expect(load).not.toHaveBeenCalled();
  await view.rerender(<Probe routeId="chat-b" target="old-b" more />);
  expect(load).toHaveBeenCalledTimes(1);
});

it("pages toward the selected result and scrolls to its latest index", async () => {
  const view = await render(<Probe target="old-a" more />);
  expect(load).toHaveBeenCalledTimes(1);
  await view.rerender(<Probe target="old-a" messages={[message("old-a"), ...initial]} />);
  await view.rerender(<Probe target="old-a" messages={[message("even-older"), message("old-a"), ...initial]} />);
  await flushFrames();
  expect(scroll).toHaveBeenCalledWith({ index: 1, animated: true, viewPosition: 0.5 });
});

it("waits for cached history revalidation before trying its first older page", async () => {
  const view = await render(<Probe target="older-hit" more chatLoading />);
  expect(load).not.toHaveBeenCalled();
  await view.rerender(<Probe target="older-hit" more />);
  expect(load).toHaveBeenCalledTimes(1);
});

it.each(["latest", "older-hit"])("cancels the prior same-chat %s target when a title result is selected", async (target) => {
  const view = await render(<Probe target={target} />);
  await act(async () => { clearChatHighlightGlobal(); });
  await view.rerender(<Probe more />);
  await flushFrames();
  expect(highlight).toBeNull();
  expect(load).not.toHaveBeenCalled();
  expect(scroll).not.toHaveBeenCalled();
});

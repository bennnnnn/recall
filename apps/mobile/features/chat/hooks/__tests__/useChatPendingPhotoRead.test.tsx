import { act, render } from "@testing-library/react-native";

import { useChatPendingPhotoRead } from "@/features/chat/hooks/useChatPendingPhotoRead";
import type { Message } from "@/lib/api";

/**
 * Review 2026-11-09: the phone locked 2 s after a reply whose photo was still on its way, back
 * at 8 s, and the photo landed at 12 s on a socket already gone: it never showed. The open chat
 * now reads itself once that wait is over, unless the photo came on its socket first.
 */
const NOW = Date.parse("2026-11-09T14:58:00Z");
const refetch = jest.fn(async () => {});

const reply = (extra: Partial<Message> = {}): Message => ({
  id: "m1", role: "assistant", content: "Ethiopia lies in the Horn of Africa.", model: null,
  created_at: "2026-11-09T14:58:00Z", ...extra,
});

function Probe({ messages, busy = false, chatId = "c1" }: { messages: Message[]; busy?: boolean; chatId?: string }) {
  useChatPendingPhotoRead({ chatId, messages, busy, refetch });
  return null;
}

async function wait(ms: number): Promise<void> {
  await act(async () => {
    jest.advanceTimersByTime(ms);
  });
}

beforeEach(() => {
  jest.useFakeTimers();
  jest.setSystemTime(NOW);
  refetch.mockClear();
});
afterEach(() => {
  jest.useRealTimers();
});

it("reads the chat once, when the photo's wait is over", async () => {
  const waiting = [reply({ photo_pending_until: NOW + 20_000 })];
  const view = await render(<Probe messages={waiting} />);
  await wait(19_999);
  expect(refetch).not.toHaveBeenCalled();
  await wait(1);
  expect(refetch).toHaveBeenCalledTimes(1);
  expect(refetch).toHaveBeenCalledWith("c1", expect.any(Function), { force: true });
  // The read changed nothing (no photo came): it is not read again.
  await view.rerender(<Probe messages={[...waiting]} />);
  await wait(60_000);
  expect(refetch).toHaveBeenCalledTimes(1);
});

it("reads nothing when the photo came on its socket first", async () => {
  const view = await render(<Probe messages={[reply({ photo_pending_until: NOW + 20_000 })]} />);
  await wait(5_000);
  await view.rerender(<Probe messages={[reply({ content: "[Image: /attachments/p/file]\n\nHi" })]} />);
  await wait(60_000);
  expect(refetch).not.toHaveBeenCalled();
});

it("waits while the page loads or a turn runs, which bring the page themselves", async () => {
  const waiting = [reply({ photo_pending_until: NOW + 1_000 })];
  const view = await render(<Probe messages={waiting} busy />);
  await wait(5_000);
  expect(refetch).not.toHaveBeenCalled();
  await view.rerender(<Probe messages={waiting} />);
  await wait(0);
  expect(refetch).toHaveBeenCalledTimes(1);
});

it("reads nothing for a thread with no photo on its way", async () => {
  await render(<Probe messages={[reply()]} />);
  await wait(60_000);
  expect(refetch).not.toHaveBeenCalled();
});

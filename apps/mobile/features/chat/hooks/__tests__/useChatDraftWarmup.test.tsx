import { act, render } from "@testing-library/react-native";

import { useChatDraftWarmup } from "@/features/chat/hooks/useChatDraftWarmup";

type Props = { chatId: string | null; composing: boolean };
const connect = jest.fn();

function Screen({ chatId, composing }: Props) {
  useChatDraftWarmup({ chatId, composing, connect });
  return null;
}

/** The screen's props over time, as the composer and the route move them. */
async function walk(steps: Props[]): Promise<void> {
  const view = await act(async () => render(<Screen {...steps[0]} />));
  for (const props of steps.slice(1)) await act(async () => { view.rerender(<Screen {...props} />); });
}

// Review 2026-11-09: with no socket opened before Send, the first message of each stretch paid
// the whole handshake (on slow cellular, a fallback to SSE). A draft's first character opens it.
describe("useChatDraftWarmup", () => {
  beforeEach(() => connect.mockClear());

  it("opens the socket at a draft's first character in an open chat, once", async () => {
    await walk([
      { chatId: "chat-1", composing: false },
      { chatId: "chat-1", composing: true },
      { chatId: "chat-1", composing: true },
    ]);
    expect(connect).toHaveBeenCalledTimes(1);
  });

  it("opens it for the new chat a first character made", async () => {
    await walk([
      { chatId: null, composing: false },
      { chatId: null, composing: true },
      { chatId: "draft-1", composing: true },
    ]);
    expect(connect).toHaveBeenCalledTimes(1);
  });

  it("opens none for a chat opened or read, with or without a saved draft", async () => {
    await walk([
      { chatId: null, composing: false },
      { chatId: "chat-1", composing: false },
      { chatId: "chat-2", composing: true },
      { chatId: null, composing: false },
      { chatId: "chat-3", composing: true },
    ]);
    expect(connect).not.toHaveBeenCalled();
  });

  it("opens it again for the next draft after a send emptied the composer", async () => {
    await walk([
      { chatId: "chat-1", composing: false },
      { chatId: "chat-1", composing: true },
      { chatId: "chat-1", composing: false },
      { chatId: "chat-1", composing: true },
    ]);
    expect(connect).toHaveBeenCalledTimes(2);
  });
});

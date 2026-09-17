import { act, renderHook } from "@testing-library/react-native";

import { useAutomationChat } from "@/hooks/useAutomationChat";
import { api } from "@/lib/api";
import type { Message } from "@/lib/api";

const mockError = jest.fn();

jest.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ token: "tok" }) }));
jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => ({ error: mockError }),
}));
jest.mock("@/lib/api", () => ({
  api: { listAllMessages: jest.fn(), setMessageFeedback: jest.fn() },
}));

const mockSetMessages = jest.fn();
jest.mock("@/hooks/useChat", () => ({
  useChat: (_token: string | null, _chatId: string | null, options: { onError?: (m: string) => void }) => ({
    messages: [],
    setMessages: mockSetMessages,
    streaming: false,
    _onError: options.onError,
  }),
}));

function msg(id: string): Message {
  return { id, role: "assistant", content: "hi", model: "smart-chat", created_at: "2026-01-01T00:00:00Z" } as Message;
}

// Stable across re-renders, matching the real caller (`useAccountViewOwner().isCurrent`) —
// a fresh arrow function per render would change the effect's deps every render.
const isCurrent = () => true;

describe("useAutomationChat", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.mocked(api.setMessageFeedback).mockResolvedValue(undefined as never);
  });

  it("seeds history from listAllMessages once per chat id", async () => {
    jest.mocked(api.listAllMessages).mockResolvedValue([msg("m1")]);
    const { result } = await renderHook((chatId: string | null) => useAutomationChat(chatId, isCurrent), {
      initialProps: "chat-1",
    });

    expect(api.listAllMessages).toHaveBeenCalledWith("tok", "chat-1");
    expect(mockSetMessages).toHaveBeenCalledWith([msg("m1")]);
    expect(result.current.loading).toBe(false);
    expect(result.current.loadError).toBe(false);
  });

  it("reports a load error without throwing", async () => {
    jest.mocked(api.listAllMessages).mockRejectedValue(new Error("boom"));
    const { result } = await renderHook((chatId: string | null) => useAutomationChat(chatId, isCurrent), {
      initialProps: "chat-2",
    });

    expect(result.current.loadError).toBe(true);
    expect(result.current.loading).toBe(false);
  });

  it("forwards message feedback to the API", async () => {
    jest.mocked(api.listAllMessages).mockResolvedValue([]);
    const { result } = await renderHook((chatId: string | null) => useAutomationChat(chatId, isCurrent), {
      initialProps: "chat-3",
    });

    await act(async () => {
      result.current.handleFeedback("m1", "up");
    });

    expect(api.setMessageFeedback).toHaveBeenCalledWith("tok", "chat-3", "m1", "up");
  });
});

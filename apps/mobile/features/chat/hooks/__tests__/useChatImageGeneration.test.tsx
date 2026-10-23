import type React from "react";
import { act, renderHook } from "@testing-library/react-native";

import { useChatImageGeneration } from "@/features/chat/hooks/useChatImageGeneration";
import { api, type Message } from "@/lib/api";
import { ApiRequestError } from "@/lib/api/errorBody";

jest.mock("@/lib/api", () => ({ api: { generateImage: jest.fn() } }));
jest.mock("@/lib/api/client", () => ({
  ApiRequestError: jest.requireActual("@/lib/api/errorBody").ApiRequestError,
}));
jest.mock("@/features/attachments/model/attachments", () => ({ uploadChatAttachment: jest.fn() }));
jest.mock("@/lib/haptics", () => ({ notifyWarning: jest.fn() }));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => null }));
jest.mock("@/lib/reportRecoverableError", () => ({ reportRecoverableError: jest.fn() }));

it.each([
  [true, "chat.image_daily_limit_paid"],
  [false, "chat.image_daily_limit_free"],
])("names the picture's own limit, not the chat allowance (isPaid %p)", async (isPaid, message) => {
  (api.generateImage as jest.Mock).mockRejectedValueOnce(
    new ApiRequestError(429, JSON.stringify({ detail: { code: "daily_limit", message: "Image limit." } })),
  );
  const updates: React.SetStateAction<Message[]>[] = [];
  const { result } = await renderHook(() => useChatImageGeneration({
    token: "tok",
    ensureChatId: async () => "chat",
    setMessages: (update) => { updates.push(update); },
    streaming: false,
    isPaid,
    isOffline: false,
    onOpenUpgrade: jest.fn(),
    onScrollToLatest: jest.fn(),
    newMessageCountRef: { current: 0 },
    t: (key: string) => key,
  }));
  await act(async () => { await result.current.submitPrompt({ prompt: "cat", userMessage: "Draw a cat" }); });
  const rows = updates.reduce<Message[]>((list, update) => (typeof update === "function" ? update(list) : update), []);
  expect(rows.at(-1)).toMatchObject({ image_gen_failure: "failed", image_gen_error: message });
});

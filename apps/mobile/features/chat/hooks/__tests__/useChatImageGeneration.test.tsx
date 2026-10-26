import type React from "react";
import { act, renderHook } from "@testing-library/react-native";

import { useChatImageGeneration } from "@/features/chat/hooks/useChatImageGeneration";
import { api, type Message } from "@/lib/api";
import { ApiRequestError } from "@/lib/api/errorBody";
import fixture from "../../../../../../docs/fixtures/error_codes.json";

jest.mock("@/lib/api", () => ({ api: { generateImage: jest.fn() } }));
jest.mock("@/lib/api/client", () => ({
  ApiRequestError: jest.requireActual("@/lib/api/errorBody").ApiRequestError,
}));
jest.mock("@/features/attachments/model/attachments", () => ({ uploadChatAttachment: jest.fn() }));
jest.mock("@/lib/haptics", () => ({ notifyWarning: jest.fn() }));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => null }));
jest.mock("@/lib/reportRecoverableError", () => ({ reportRecoverableError: jest.fn() }));

async function failedRow(isPaid: boolean, error: Error): Promise<Message | undefined> {
  (api.generateImage as jest.Mock).mockRejectedValueOnce(error);
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
  return rows.at(-1);
}

const refusal = (status: number, code: string, message: string) =>
  new ApiRequestError(status, JSON.stringify({ detail: { code, message } }));

it.each([
  [true, "chat.image_daily_limit_paid"],
  [false, "chat.image_daily_limit_free"],
])("names the picture's own limit, not the chat allowance (isPaid %p)", async (isPaid, message) => {
  const row = await failedRow(isPaid, refusal(429, "daily_limit", "Image limit."));
  // Retry would meet the same cap until tomorrow: the card offers none.
  expect(row).toMatchObject({ image_gen_failure: "failed", image_gen_error: message, image_gen_refused: true });
});

it("offers no Retry for a picture the content rules refused", async () => {
  const row = await failedRow(true, refusal(422, "content_blocked", "Blocked."));
  expect(row).toMatchObject({ image_gen_error: "chat.image_content_blocked", image_gen_refused: true });
});

it.each([
  ["a provider failure", refusal(502, "upstream_failed", "Could not generate image")],
  ["a dropped connection", new Error("Network request failed")],
])("keeps Retry after %s", async (_label, error) => {
  const row = await failedRow(true, error);
  expect(row).toMatchObject({ image_gen_failure: "failed", image_gen_refused: undefined });
});

// The image service's 502 (modules/images/generation.py) showed its English on the card.
it("words a provider failure in the phone's language", async () => {
  const failed = fixture.image_upstream_failed;
  const row = await failedRow(false, refusal(failed.status, failed.detail.code, failed.detail.message));
  expect(row).toMatchObject({ image_gen_error: "chat.image_gen_failed", image_gen_refused: undefined });
});

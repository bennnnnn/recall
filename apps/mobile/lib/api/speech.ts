import { request } from "@/lib/api/client";
import { streamLiveTalkSpeak } from "@/lib/liveTalkStream";
import type { LiveTalkStatus } from "@/lib/liveTalkLogic";

export const speechApi = {
  liveTalkStatus: (token: string) => request<LiveTalkStatus>("/speech/live", token),
  refundLiveTalkTurn: (token: string) =>
    request<LiveTalkStatus>("/speech/live/refund", token, { method: "POST" }),
  liveTalkSpeak: streamLiveTalkSpeak,
  persistRealtimeLiveTalkTurn: (
    token: string,
    body: { chatId: string; userText: string; assistantText: string },
  ) =>
    request<void>("/speech/live/persist", token, {
      method: "POST",
      body: JSON.stringify({
        chat_id: body.chatId,
        user_text: body.userText,
        assistant_text: body.assistantText,
      }),
    }),
};
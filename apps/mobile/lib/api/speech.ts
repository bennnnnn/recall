import { request } from "@/lib/api/client";
import { streamLiveTalkSpeak } from "@/lib/liveTalkStream";
import type { LiveTalkStatus } from "@/lib/liveTalkLogic";

export const speechApi = {
  liveTalkStatus: (token: string) => request<LiveTalkStatus>("/speech/live", token),
  refundLiveTalkTurn: (token: string) =>
    request<LiveTalkStatus>("/speech/live/refund", token, { method: "POST" }),
  liveTalkSpeak: streamLiveTalkSpeak,
  exchangeRealtimeSdp: (
    token: string,
    body: { sdp: string; chatId?: string | null },
  ) =>
    request<{ sdp: string; call_id?: string | null; model: string }>(
      "/speech/live/webrtc",
      token,
      {
        method: "POST",
        body: JSON.stringify({
          sdp: body.sdp,
          ...(body.chatId ? { chat_id: body.chatId } : {}),
        }),
      },
      true,
      15_000,
    ),
  persistRealtimeLiveTalkTurn: (
    token: string,
    body: { chatId: string; callId: string; userText: string; assistantText: string },
  ) =>
    request<void>("/speech/live/persist", token, {
      method: "POST",
      body: JSON.stringify({
        chat_id: body.chatId,
        call_id: body.callId,
        user_text: body.userText,
        assistant_text: body.assistantText,
      }),
    }),
};
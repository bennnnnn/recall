import { request } from "@/lib/api/client";
import type { LiveTalkStatus } from "@/lib/liveTalkLogic";
import type { Message, SearchSource } from "@/lib/api/types";

export type RealtimeSessionCredential = {
  client_secret: string;
  expires_at: number;
  call_id: string;
  model: string;
};

export const speechApi = {
  liveTalkStatus: (token: string) => request<LiveTalkStatus>("/speech/live", token),
  createRealtimeSession: (token: string, body: { chatId?: string | null; bargeIn?: boolean }) =>
    request<RealtimeSessionCredential>(
      "/speech/live/session",
      token,
      {
        method: "POST",
        body: JSON.stringify({
          ...(body.chatId ? { chat_id: body.chatId } : {}),
          barge_in: body.bargeIn ?? false,
          tools_enabled: Boolean(body.chatId),
        }),
      },
      true,
      15_000,
    ),
  persistRealtimeLiveTalkTurn: (
    token: string,
    body: { chatId: string; callId: string; userText: string; assistantText: string; turnId?: string },
  ) =>
    request<{ user_message: Message | null; assistant_message: Message | null } | undefined>("/speech/live/persist", token, {
      method: "POST",
      body: JSON.stringify({
        chat_id: body.chatId,
        call_id: body.callId,
        user_text: body.userText,
        assistant_text: body.assistantText,
        turn_id: body.turnId,
        return_messages: true,
      }),
    }),
  realtimeTool: (token: string, body: {
    chat_id: string; call_id: string; turn_id: string;
    name: "memory_lookup" | "web_search"; query: string;
  }) => request<{ content: string; sources?: SearchSource[] }>("/speech/live/tool", token, {
    method: "POST", body: JSON.stringify(body),
  }, true, 15_000),
};

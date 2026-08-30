import { request } from "@/lib/api/client";
import { streamLiveTalkSpeak } from "@/lib/liveTalkStream";
import type { LiveTalkStatus } from "@/lib/liveTalkLogic";

export const speechApi = {
  liveTalkStatus: (token: string) => request<LiveTalkStatus>("/speech/live", token),
  refundLiveTalkTurn: (token: string) =>
    request<LiveTalkStatus>("/speech/live/refund", token, { method: "POST" }),
  liveTalkSpeak: streamLiveTalkSpeak,
};

import { request } from "@/lib/api/client";
import { streamLiveTalkSpeak } from "@/lib/liveTalkStream";
import type { LiveTalkStatus } from "@/lib/liveTalkLogic";

export const speechApi = {
  liveTalkStatus: (token: string) => request<LiveTalkStatus>("/speech/live", token),
  reserveLiveTalkTurn: (token: string) =>
    request<LiveTalkStatus>("/speech/live/turn", token, { method: "POST" }),
  refundLiveTalkTurn: (token: string) =>
    request<LiveTalkStatus>("/speech/live/refund", token, { method: "POST" }),
  commitLiveTalkTurn: (token: string) =>
    request<LiveTalkStatus>("/speech/live/commit", token, { method: "POST" }),
  liveTalkSpeak: streamLiveTalkSpeak,
};

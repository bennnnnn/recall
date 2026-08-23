import { request } from "@/lib/api/client";
import type { LiveTalkStatus } from "@/lib/liveTalkLogic";

export type LiveTalkSpeakResult = {
  audio_base64: string;
  content_type: string;
  transcript: string;
  remaining: number;
  limit: number;
};

export const speechApi = {
  liveTalkStatus: (token: string) => request<LiveTalkStatus>("/speech/live", token),
  reserveLiveTalkTurn: (token: string) =>
    request<LiveTalkStatus>("/speech/live/turn", token, { method: "POST" }),
  refundLiveTalkTurn: (token: string) =>
    request<LiveTalkStatus>("/speech/live/refund", token, { method: "POST" }),
  commitLiveTalkTurn: (token: string) =>
    request<LiveTalkStatus>("/speech/live/commit", token, { method: "POST" }),
  liveTalkSpeak: (
    token: string,
    audioBase64: string,
    filename: string,
  ): Promise<LiveTalkSpeakResult> =>
    request<LiveTalkSpeakResult>(
      "/speech/live/speak",
      token,
      {
        method: "POST",
        body: JSON.stringify({ audio_base64: audioBase64, filename }),
      },
      true,
      60_000,
    ),
};

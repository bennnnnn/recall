import Constants from "expo-constants";
import { Platform } from "react-native";

import { analyticsApi, type ProductEventName } from "@/lib/api/analytics";
import { getToken } from "@/lib/auth";
import { getInstallationId } from "@/lib/installationId";

export type ChatTtftBucket =
  | "lt500"
  | "500_999"
  | "1000_1999"
  | "2000_3999"
  | "4000_5999"
  | "6000_plus";

export type ChatTransport = "ws" | "sse";

type Sample = {
  latencyBucket: ChatTtftBucket;
  transport: ChatTransport;
  hasAttachment: boolean;
};

/** How a chat turn ended (`chat_turn_outcome`): enumerated values only, never text. */
export type ChatTurnOutcomeProperties = {
  completion: "complete" | "stopped" | "interrupted" | "error";
  error_code: string;
  tool: string;
};

/** Loaded lazily by the chat model, after the moment it measures. */
async function recordChatEvent(
  name: ProductEventName,
  properties: Record<string, string>,
): Promise<void> {
  const platform = Platform.OS;
  if (platform !== "ios" && platform !== "android" && platform !== "web") return;
  const token = await getToken();
  if (!token) return;
  const installationId = await getInstallationId();
  await analyticsApi.recordProductEvents(token, [
    {
      name,
      properties,
      platform,
      app_version: Constants.expoConfig?.version,
      installation_id: installationId ?? undefined,
      client_at: new Date().toISOString(),
    },
  ]);
}

/** Fire-and-forget caller; all work here happens after first-token delivery. */
export async function reportChatTtft(sample: Sample): Promise<void> {
  await recordChatEvent("chat_ttft", {
    latency_bucket: sample.latencyBucket,
    transport: sample.transport,
    has_attachment: sample.hasAttachment ? "yes" : "no",
  });
}

/** Fire-and-forget caller; sent once the turn has ended. */
export async function reportChatTurnOutcome(properties: ChatTurnOutcomeProperties): Promise<void> {
  await recordChatEvent("chat_turn_outcome", properties);
}

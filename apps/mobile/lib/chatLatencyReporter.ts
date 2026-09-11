import Constants from "expo-constants";
import { Platform } from "react-native";

import { analyticsApi } from "@/lib/api/analytics";
import { getToken } from "@/lib/auth";
import type { ChatTransport, ChatTtftBucket } from "@/lib/chatLatency";
import { getInstallationId } from "@/lib/installationId";

type Sample = {
  latencyBucket: ChatTtftBucket;
  transport: ChatTransport;
  hasAttachment: boolean;
};

/** Fire-and-forget caller; all work here happens after first-token delivery. */
export async function reportChatTtft(sample: Sample): Promise<void> {
  const platform = Platform.OS;
  if (platform !== "ios" && platform !== "android" && platform !== "web") return;
  const token = await getToken();
  if (!token) return;
  const installationId = await getInstallationId();
  await analyticsApi.recordProductEvents(token, [
    {
      name: "chat_ttft",
      properties: {
        latency_bucket: sample.latencyBucket,
        transport: sample.transport,
        has_attachment: sample.hasAttachment ? "yes" : "no",
      },
      platform,
      app_version: Constants.expoConfig?.version,
      installation_id: installationId ?? undefined,
      client_at: new Date().toISOString(),
    },
  ]);
}

import Constants from "expo-constants";
import { Platform } from "react-native";

import { api, type ProductEventName } from "@/lib/api";
import { getInstallationId } from "@/lib/installationId";

function analyticsPlatform(): "ios" | "android" | "web" | null {
  if (Platform.OS === "ios" || Platform.OS === "android" || Platform.OS === "web") {
    return Platform.OS;
  }
  return null;
}

/**
 * Record a metadata-only product event. This is intentionally fire-and-forget:
 * analytics must never delay or fail the user action being measured.
 */
export function trackProductEvent(
  token: string | null,
  name: ProductEventName,
  properties: Record<string, string> = {},
): void {
  if (!token) return;
  const platform = analyticsPlatform();
  if (!platform) return;

  void (async () => {
    const installationId = await getInstallationId();
    await api.recordProductEvents(token, [
      {
        name,
        properties,
        platform,
        app_version: Constants.expoConfig?.version,
        installation_id: installationId ?? undefined,
        client_at: new Date().toISOString(),
      },
    ]);
  })().catch(() => {
    // Best-effort by design; product telemetry never blocks the app.
  });
}

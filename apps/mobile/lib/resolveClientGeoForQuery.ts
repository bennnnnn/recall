import { Alert, Linking } from "react-native";

import type { ClientGeo } from "@/lib/clientGeo";
import { requestDeviceGeo } from "@/lib/deviceLocation";
import { isAmbiguousLocalPlacesQuery, isGeoQuery } from "@/lib/localPlacesQuery";

export type ClientGeoResolveResult =
  | { ok: true; clientGeo: ClientGeo | null }
  | { ok: false };

type Translate = (key: string, options?: Record<string, unknown>) => string;

function formatCoordLabel(latitude: number, longitude: number): string {
  return `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`;
}

function alertOpenSettings(t: Translate): void {
  Alert.alert(t("chat.location_required_title"), t("chat.location_required_body"), [
    { text: t("common.cancel"), style: "cancel" },
    {
      text: t("chat.location_open_settings"),
      onPress: () => {
        void Linking.openSettings();
      },
    },
  ]);
}

/**
 * Resolve device geo for nearby / where-am-I asks.
 * Shows the system permission sheet directly (no custom pre-prompt).
 * Only offers Open Settings when the OS will not show that sheet again.
 */
export async function resolveClientGeoForQuery(
  _token: string,
  queryText: string,
  t: Translate,
  mergeUser: (patch: { location: string; location_enabled: boolean }) => void,
): Promise<ClientGeoResolveResult> {
  if (!queryText || !isGeoQuery(queryText) || isAmbiguousLocalPlacesQuery(queryText)) {
    return { ok: true, clientGeo: null };
  }

  const result = await requestDeviceGeo();

  if (result.status === "granted") {
    const label =
      result.geo.label?.trim() ||
      formatCoordLabel(result.geo.latitude, result.geo.longitude);
    const clientGeo: ClientGeo = {
      label,
      latitude: result.geo.latitude,
      longitude: result.geo.longitude,
    };
    mergeUser({ location: clientGeo.label, location_enabled: true });
    return { ok: true, clientGeo };
  }

  if (result.status === "blocked") {
    alertOpenSettings(t);
    return { ok: false };
  }

  if (result.status === "expo_go") {
    Alert.alert(t("chat.location_required_title"), t("settings.location_expo_go"));
    return { ok: false };
  }

  if (result.status === "error") {
    Alert.alert(t("chat.location_required_title"), t("settings.location_denied"));
    return { ok: false };
  }

  // Soft deny on the system sheet — don't bounce the user to Settings.
  return { ok: false };
}

import { Alert, Linking } from "react-native";

import type { ClientGeo } from "@/lib/clientGeo";
import { requestDeviceGeo } from "@/lib/deviceLocation";
import { isAmbiguousLocalPlacesQuery, isGeoQuery } from "@/lib/localPlacesQuery";

export type ClientGeoResolveResult =
  | { ok: true; clientGeo: ClientGeo | null }
  | { ok: false };

type Translate = (key: string, options?: Record<string, unknown>) => string;

type PersistLocation = (patch: {
  location: string;
  location_enabled: boolean;
}) => void | Promise<void>;

function formatCoordLabel(latitude: number, longitude: number): string {
  return `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`;
}

function alertOpenDeviceSettings(t: Translate): void {
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

/** Ask to enable Location here (same as the Preferences switch), without leaving chat. */
function promptEnableLocation(t: Translate): Promise<boolean> {
  return new Promise((resolve) => {
    Alert.alert(t("chat.location_required_title"), t("chat.location_disabled_body"), [
      {
        text: t("common.cancel"),
        style: "cancel",
        onPress: () => resolve(false),
      },
      {
        text: t("chat.location_turn_on"),
        onPress: () => resolve(true),
      },
    ]);
  });
}

/**
 * Resolve device geo for nearby / where-am-I asks.
 * If the in-app Location toggle is off, offers Turn on here (no Settings hop).
 * Only offers device Settings when the OS will not show the permission sheet again.
 */
export async function resolveClientGeoForQuery(
  _token: string,
  queryText: string,
  t: Translate,
  persistLocation: PersistLocation,
  locationEnabled = false,
): Promise<ClientGeoResolveResult> {
  if (!queryText || !isGeoQuery(queryText) || isAmbiguousLocalPlacesQuery(queryText)) {
    return { ok: true, clientGeo: null };
  }

  if (!locationEnabled) {
    const turnOn = await promptEnableLocation(t);
    if (!turnOn) return { ok: false };
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
    try {
      await persistLocation({ location: clientGeo.label, location_enabled: true });
    } catch {
      // Still use this turn's fix; Settings may catch up on next refresh.
    }
    return { ok: true, clientGeo };
  }

  if (result.status === "blocked") {
    alertOpenDeviceSettings(t);
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

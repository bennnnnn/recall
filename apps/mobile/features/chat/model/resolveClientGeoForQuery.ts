import { Linking } from "react-native";

import { getSessionGeneration } from "@/lib/auth";
import type { ClientGeo } from "@/features/chat/model/clientGeo";
import { hasLocationPermission, requestDeviceGeo } from "@/lib/deviceLocation";
import { isAmbiguousLocalPlacesQuery, isGeoQuery } from "@/lib/places/localPlacesQuery";
import { alertDialog, confirmDialog } from "@/ui/overlay/dialogs";

type ClientGeoResolveResult =
  | { ok: true; clientGeo: ClientGeo | null }
  | { ok: false };

type Translate = (key: string, options?: Record<string, unknown>) => string;

type PersistLocation = (patch: {
  location?: string;
  location_enabled?: boolean;
}) => void | Promise<void>;

export function queryNeedsClientGeo(queryText: string): boolean {
  return Boolean(
    queryText &&
      isGeoQuery(queryText) &&
      !isAmbiguousLocalPlacesQuery(queryText),
  );
}

function formatCoordLabel(latitude: number, longitude: number): string {
  return `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`;
}

function alertOpenDeviceSettings(t: Translate): void {
  void confirmDialog({
    title: t("chat.location_required_title"),
    message: t("chat.location_required_body"),
    cancelLabel: t("common.cancel"),
    confirmLabel: t("chat.location_open_settings"),
  }).then((ok) => {
    if (!ok) return;
    void Linking.openSettings();
  });
}

/**
 * Resolve device geo for nearby / where-am-I asks.
 * Show the system permission sheet immediately — do not ask the model for a city,
 * and do not insert an in-app "Turn on" alert in front of the OS prompt.
 * Location switched off while the phone already allows it is the user's choice, never
 * undone here: nothing is read or sent, and the server's reply asks for the place.
 * Before the server has said (`locationOn` null, the launch cache) a fix goes with the
 * turn and nothing is saved: the server applies the switch.
 * A recent fix serves, and the waits are bounded: with no fix in time the turn
 * goes without one. `persistLocation` is awaited only as far as it says: the
 * caller decides whether the turn must wait for the profile to save. Coordinates
 * alone never replace the profile's place: a name that comes after the turn
 * went saves then, for the account that asked.
 */
export async function resolveClientGeoForQuery(
  _token: string,
  queryText: string,
  t: Translate,
  persistLocation: PersistLocation,
  locationOn: boolean | null,
): Promise<ClientGeoResolveResult> {
  if (!queryNeedsClientGeo(queryText)) {
    return { ok: true, clientGeo: null };
  }

  const allowedBefore = locationOn === true || (await hasLocationPermission());
  if (locationOn === false && allowedBefore) {
    return { ok: true, clientGeo: null };
  }

  const session = getSessionGeneration();
  const result = await requestDeviceGeo({ quick: true });

  if (result.status === "no_fix") {
    return { ok: true, clientGeo: null };
  }

  if (result.status === "granted") {
    const { geo } = result;
    const place = geo.label?.trim() || null;
    const clientGeo: ClientGeo = {
      label: place ?? formatCoordLabel(geo.latitude, geo.longitude),
      latitude: geo.latitude,
      longitude: geo.longitude,
    };
    // The switch is the user's: only their Allow on the system sheet, just now, turns it on.
    // One that is on keeps its place fresh; one not yet read from the server saves nothing.
    const justAllowed = !allowedBefore;
    if (!justAllowed && locationOn !== true) return { ok: true, clientGeo };
    const named = place ? { location: place } : null;
    try {
      if (justAllowed) await persistLocation({ ...named, location_enabled: true });
      else if (named) await persistLocation(named);
    } catch {
      // Still use this turn's fix; Settings may catch up on next refresh.
    }
    void geo.lateLabel
      ?.then((late) => {
        const name = late?.trim();
        if (name && session === getSessionGeneration()) return persistLocation({ location: name });
      })
      .catch(() => undefined);
    return { ok: true, clientGeo };
  }

  if (result.status === "blocked") {
    alertOpenDeviceSettings(t);
    return { ok: false };
  }

  if (result.status === "expo_go") {
    void alertDialog({
      title: t("chat.location_required_title"),
      message: t("settings.location_expo_go"),
    });
    return { ok: false };
  }

  if (result.status === "error") {
    void alertDialog({
      title: t("chat.location_required_title"),
      message: t("settings.location_denied"),
    });
    return { ok: false };
  }

  // Soft deny on the system sheet — don't bounce the user to Settings.
  return { ok: false };
}

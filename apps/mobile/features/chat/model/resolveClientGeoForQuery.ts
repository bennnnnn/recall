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

type LocationPatch = { location?: string; location_enabled?: true };

type PersistLocation = (patch: LocationPatch) => void | Promise<void>;

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
 * The account's Location switch as the server last said it. Never chosen (null on the
 * server) asks through the system sheet; off is the user's own choice in Data controls;
 * "unknown" before the server has said (the launch cache holds no switch).
 */
export type LocationSwitch = "on" | "off" | "never_chosen" | "unknown";

export function locationSwitchOf(enabled: boolean | null | undefined, confirmed: boolean): LocationSwitch {
  if (!confirmed) return "unknown";
  if (enabled === true) return "on";
  return enabled === false ? "off" : "never_chosen";
}

/**
 * What a fix saves to the profile. Only the user turns Location on: their Allow on the
 * system sheet, or a fix for a switch never chosen (the flow before there was a choice).
 * One that is on keeps its place fresh; a switch not yet read saves nothing.
 */
function locationPatch(locationSwitch: LocationSwitch, justAllowed: boolean, place: string | null): LocationPatch | null {
  const named = place ? { location: place } : {};
  if (locationSwitch === "never_chosen" || justAllowed) return { ...named, location_enabled: true };
  return locationSwitch === "on" && place ? named : null;
}

/**
 * Resolve device geo for nearby / where-am-I asks.
 * Show the system permission sheet immediately — do not ask the model for a city,
 * and do not insert an in-app "Turn on" alert in front of the OS prompt.
 * Location switched off is the user's choice, never undone here: nothing is read or
 * sent, and the server's reply asks for the place. Before the server has said
 * (`unknown`), a fix the phone already allows goes with the turn and nothing is
 * saved: the server applies the switch.
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
  locationSwitch: LocationSwitch,
): Promise<ClientGeoResolveResult> {
  if (!queryNeedsClientGeo(queryText) || locationSwitch === "off") {
    return { ok: true, clientGeo: null };
  }

  const allowedBefore = locationSwitch !== "unknown" || (await hasLocationPermission());
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
    const patch = locationPatch(locationSwitch, !allowedBefore, place);
    if (!patch && locationSwitch !== "on") return { ok: true, clientGeo };
    try {
      if (patch) await persistLocation(patch);
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

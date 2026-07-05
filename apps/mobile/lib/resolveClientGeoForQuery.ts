import { Alert } from "react-native";

import type { ClientGeo } from "@/lib/clientGeo";
import { confirmGeoLocationAccess } from "@/lib/confirmGeoLocation";
import { ensureNearbyLocation } from "@/lib/ensureNearbyLocation";
import { isAmbiguousLocalPlacesQuery, isGeoQuery } from "@/lib/localPlacesQuery";

export type ClientGeoResolveResult =
  | { ok: true; clientGeo: ClientGeo | null }
  | { ok: false };

type Translate = (key: string, options?: Record<string, unknown>) => string;

/** Prompt for location when needed and resolve nearby geo for a user query. */
export async function resolveClientGeoForQuery(
  token: string,
  queryText: string,
  t: Translate,
  mergeUser: (patch: { location: string; location_enabled: boolean }) => void,
): Promise<ClientGeoResolveResult> {
  if (!queryText || !isGeoQuery(queryText) || isAmbiguousLocalPlacesQuery(queryText)) {
    return { ok: true, clientGeo: null };
  }

  const allowed = await confirmGeoLocationAccess(t);
  if (!allowed) return { ok: false };

  const clientGeo = await ensureNearbyLocation(token, queryText);
  if (!clientGeo) {
    Alert.alert(t("chat.location_required_title"), t("chat.location_required_body"));
    return { ok: false };
  }

  mergeUser({ location: clientGeo.label, location_enabled: true });
  return { ok: true, clientGeo };
}

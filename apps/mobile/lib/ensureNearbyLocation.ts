import { api } from "@/lib/api";
import type { ClientGeo } from "@/lib/clientGeo";
import { getDeviceGeo } from "@/lib/deviceLocation";
import { isAmbiguousLocalPlacesQuery, isGeoQuery } from "@/lib/localPlacesQuery";

function formatCoordLabel(latitude: number, longitude: number): string {
  return `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`;
}

/** Always request fresh GPS for geo queries — never reuse a stale profile city. */
export async function ensureNearbyLocation(
  token: string,
  text: string,
): Promise<ClientGeo | null> {
  if (!isGeoQuery(text) || isAmbiguousLocalPlacesQuery(text)) return null;

  const geo = await getDeviceGeo();
  if (!geo) return null;

  const label = geo.label?.trim() || formatCoordLabel(geo.latitude, geo.longitude);
  const clientGeo: ClientGeo = {
    label,
    latitude: geo.latitude,
    longitude: geo.longitude,
  };

  try {
    await api.updateMe(token, { location: label, location_enabled: true });
  } catch {
    // Still send ephemeral client location even if profile sync fails.
  }
  return clientGeo;
}

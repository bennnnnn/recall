import type { ClientGeo } from "@/lib/clientGeo";
import { getDeviceGeo } from "@/lib/deviceLocation";
import { isAmbiguousLocalPlacesQuery, isGeoQuery } from "@/lib/localPlacesQuery";

function formatCoordLabel(latitude: number, longitude: number): string {
  return `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`;
}

/** Always request fresh GPS for geo queries — never reuse a stale profile city.

The fresh location is sent per-request as ephemeral `client_location` /
lat-lng on the WS message; it is NOT written to the user's profile. Profile
location changes only from Settings, so asking "restaurants nearby?" while
traveling no longer overwrites the user's saved home city. */
export async function ensureNearbyLocation(
  token: string,
  text: string,
): Promise<ClientGeo | null> {
  if (!isGeoQuery(text) || isAmbiguousLocalPlacesQuery(text)) return null;

  const geo = await getDeviceGeo();
  if (!geo) return null;

  const label = geo.label?.trim() || formatCoordLabel(geo.latitude, geo.longitude);
  return {
    label,
    latitude: geo.latitude,
    longitude: geo.longitude,
  };
}

import { canUseDeviceLocation } from "@/lib/expoRuntime";

export type DeviceGeo = {
  label: string | null;
  latitude: number;
  longitude: number;
};

export type DeviceGeoRequestResult =
  | { status: "granted"; geo: DeviceGeo }
  /** User declined the system sheet; iOS may still allow asking again later. */
  | { status: "denied" }
  /** Permission permanently denied — only Settings can re-enable. */
  | { status: "blocked" }
  /** Running in Expo Go (no native location entitlement). */
  | { status: "expo_go" }
  /** Unexpected native failure after permission was available. */
  | { status: "error" };

type ExpoLocationModule = typeof import("expo-location");

async function readDeviceGeo(Location: ExpoLocationModule): Promise<DeviceGeo> {
  const pos = await Location.getCurrentPositionAsync({
    accuracy: Location.Accuracy.Balanced,
  });
  const { latitude, longitude } = pos.coords;

  let label: string | null = null;
  try {
    const places = await Location.reverseGeocodeAsync({ latitude, longitude });
    const place = places[0];
    if (place) {
      const parts = [place.city, place.region, place.country].filter(
        (p): p is string => Boolean(p?.trim()),
      );
      if (parts.length > 0) label = parts.join(", ");
    }
  } catch {
    // Coordinates alone are enough for the backend.
  }

  return { label, latitude, longitude };
}

/**
 * Request location the way other apps do: show the system permission sheet
 * when possible. Only report `blocked` when the OS will not show that sheet again.
 */
export async function requestDeviceGeo(): Promise<DeviceGeoRequestResult> {
  if (!canUseDeviceLocation()) {
    return { status: "expo_go" };
  }

  try {
    const Location = await import("expo-location");
    const current = await Location.getForegroundPermissionsAsync();

    if (current.status === "granted") {
      return { status: "granted", geo: await readDeviceGeo(Location) };
    }

    // System Allow / Don't Allow sheet — only while the OS still permits it.
    if (current.status === "undetermined" || current.canAskAgain) {
      const req = await Location.requestForegroundPermissionsAsync();
      if (req.status === "granted") {
        return { status: "granted", geo: await readDeviceGeo(Location) };
      }
      return req.canAskAgain === false ? { status: "blocked" } : { status: "denied" };
    }

    return { status: "blocked" };
  } catch {
    return { status: "error" };
  }
}

/** GPS coordinates + optional city/region from reverse geocode. */
export async function getDeviceGeo(): Promise<DeviceGeo | null> {
  const result = await requestDeviceGeo();
  return result.status === "granted" ? result.geo : null;
}

/** City/region label from device GPS + reverse geocode, or null if unavailable. */
export async function getDeviceLocationLabel(): Promise<string | null> {
  const geo = await getDeviceGeo();
  return geo?.label ?? null;
}

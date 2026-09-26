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

type GeoRun<T> =
  | { status: "granted"; value: T }
  | { status: "denied" | "blocked" | "expo_go" | "error" };

/**
 * Shared permission flow: show the system sheet when the OS still allows it,
 * then run the read. Only `blocked` means the sheet can never appear again.
 */
async function runWithLocationPermission<T>(
  read: (Location: ExpoLocationModule) => Promise<T>,
): Promise<GeoRun<T>> {
  if (!canUseDeviceLocation()) {
    return { status: "expo_go" };
  }

  try {
    const Location = await import("expo-location");
    const current = await Location.getForegroundPermissionsAsync();

    if (current.status === "granted") {
      return { status: "granted", value: await read(Location) };
    }

    // System Allow / Don't Allow sheet — only while the OS still permits it.
    if (current.status === "undetermined" || current.canAskAgain) {
      const req = await Location.requestForegroundPermissionsAsync();
      if (req.status === "granted") {
        return { status: "granted", value: await read(Location) };
      }
      return req.canAskAgain === false ? { status: "blocked" } : { status: "denied" };
    }

    return { status: "blocked" };
  } catch {
    return { status: "error" };
  }
}

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
  const result = await runWithLocationPermission(readDeviceGeo);
  if (result.status !== "granted") return { status: result.status };
  return { status: "granted", geo: result.value };
}

/** GPS coordinates + optional city/region from reverse geocode. */
export async function getDeviceGeo(): Promise<DeviceGeo | null> {
  const result = await requestDeviceGeo();
  return result.status === "granted" ? result.geo : null;
}

/** Structured reverse-geocode parts for pickers (city / region / country). */
export type DevicePlace = {
  city: string | null;
  region: string | null;
  country: string | null;
};

export type DevicePlaceRequestResult =
  | { status: "granted"; place: DevicePlace }
  | { status: "denied" }
  | { status: "blocked" }
  | { status: "expo_go" }
  | { status: "error" };

async function readDevicePlace(Location: ExpoLocationModule): Promise<DevicePlace> {
  const pos = await Location.getCurrentPositionAsync({
    accuracy: Location.Accuracy.Balanced,
  });
  const places = await Location.reverseGeocodeAsync({
    latitude: pos.coords.latitude,
    longitude: pos.coords.longitude,
  });
  const place = places[0];
  return {
    city: place?.city?.trim() || null,
    region: place?.region?.trim() || null,
    country: place?.country?.trim() || null,
  };
}

/** City / region / country from device GPS, for structured location fields. */
export async function requestDevicePlace(): Promise<DevicePlaceRequestResult> {
  const result = await runWithLocationPermission(readDevicePlace);
  if (result.status !== "granted") return { status: result.status };
  return { status: "granted", place: result.value };
}

/** City/region label from device GPS + reverse geocode, or null if unavailable. */
export async function getDeviceLocationLabel(): Promise<string | null> {
  const geo = await getDeviceGeo();
  return geo?.label ?? null;
}

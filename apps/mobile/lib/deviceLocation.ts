import { canUseDeviceLocation } from "@/lib/expoRuntime";

type DeviceGeo = {
  label: string | null;
  latitude: number;
  longitude: number;
};

type DeviceGeoRequestResult =
  | { status: "granted"; geo: DeviceGeo }
  /** A quick read found no recent fix and no new one in time: go without one. */
  | { status: "no_fix" }
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

/** A fix this recent and this close answers "near me" or "where am I" without a new one. */
const RECENT_FIX_MAX_AGE_MS = 5 * 60_000;
const RECENT_FIX_ACCURACY_M = 500;
/** With no recent fix, how long a send waits for a new one before going without. */
const NEW_FIX_TIMEOUT_MS = 5_000;
/** The place name is a nicety: coordinates alone serve the server. */
const PLACE_NAME_TIMEOUT_MS = 1_500;

/** `work`'s value, or null once `ms` pass first. */
function within<T>(work: Promise<T>, ms: number): Promise<T | null> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => resolve(null), ms);
    work.then(
      (value) => { clearTimeout(timer); resolve(value); },
      (error: unknown) => { clearTimeout(timer); reject(error); },
    );
  });
}

async function recentFix(Location: ExpoLocationModule) {
  try {
    return await Location.getLastKnownPositionAsync({
      maxAge: RECENT_FIX_MAX_AGE_MS,
      requiredAccuracy: RECENT_FIX_ACCURACY_M,
    });
  } catch {
    return null;
  }
}

async function placeName(
  Location: ExpoLocationModule,
  latitude: number,
  longitude: number,
  quick: boolean,
): Promise<string | null> {
  try {
    const lookup = Location.reverseGeocodeAsync({ latitude, longitude });
    const place = (quick ? await within(lookup, PLACE_NAME_TIMEOUT_MS) : await lookup)?.[0];
    if (!place) return null;
    const parts = [place.city, place.region, place.country].filter(
      (p): p is string => Boolean(p?.trim()),
    );
    return parts.length > 0 ? parts.join(", ") : null;
  } catch {
    // Coordinates alone are enough for the backend.
    return null;
  }
}

/**
 * A new fix, or for a `quick` read (a chat send) a recent one when there is
 * one, and null when none comes within `NEW_FIX_TIMEOUT_MS`.
 */
async function readDeviceGeo(Location: ExpoLocationModule, quick: boolean): Promise<DeviceGeo | null> {
  const newFix = () => Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
  const pos = quick
    ? (await recentFix(Location)) ?? (await within(newFix(), NEW_FIX_TIMEOUT_MS))
    : await newFix();
  if (!pos) return null;
  const { latitude, longitude } = pos.coords;
  return { label: await placeName(Location, latitude, longitude, quick), latitude, longitude };
}

/**
 * Request location the way other apps do: show the system permission sheet
 * when possible. Only report `blocked` when the OS will not show that sheet again.
 * `quick` (a chat send) takes a recent fix and bounds the waits; Settings asks
 * for a new fix and waits for it.
 */
export async function requestDeviceGeo(options: { quick?: boolean } = {}): Promise<DeviceGeoRequestResult> {
  const result = await runWithLocationPermission((Location) => readDeviceGeo(Location, options.quick === true));
  if (result.status !== "granted") return { status: result.status };
  return result.value ? { status: "granted", geo: result.value } : { status: "no_fix" };
}

/** GPS coordinates + optional city/region from reverse geocode. */
async function getDeviceGeo(): Promise<DeviceGeo | null> {
  const result = await requestDeviceGeo();
  return result.status === "granted" ? result.geo : null;
}

/** City/region label from device GPS + reverse geocode, or null if unavailable. */
export async function getDeviceLocationLabel(): Promise<string | null> {
  const geo = await getDeviceGeo();
  return geo?.label ?? null;
}

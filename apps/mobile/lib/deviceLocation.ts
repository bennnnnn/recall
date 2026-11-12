import { canUseDeviceLocation } from "@/lib/expoRuntime";

type DeviceGeo = {
  label: string | null;
  latitude: number;
  longitude: number;
  /** A quick read's place name that missed its wait: the lookup's own result, when it ends. */
  lateLabel?: Promise<string | null>;
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
 * `ask: false` (a background read, such as the hourly sync on app open) never
 * shows the sheet: without permission it reads nothing and reports `denied`.
 */
async function runWithLocationPermission<T>(
  read: (Location: ExpoLocationModule) => Promise<T>,
  ask = true,
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
    if (!ask) return { status: "denied" };

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

/** The phone already lets Recall read the location: asking would show no system sheet. */
export async function hasLocationPermission(): Promise<boolean> {
  if (!canUseDeviceLocation()) return false;
  try {
    const Location = await import("expo-location");
    return (await Location.getForegroundPermissionsAsync()).status === "granted";
  } catch {
    // Read as not allowed: a geo ask then goes the asking way, which says what failed.
    console.warn("[location] permission could not be read");
    return false;
  }
}

/**
 * The phone does not let Recall read its location now (denied, or turned off in Settings).
 * Not asked yet, or a build that cannot read it (Expo Go), is not a denial.
 */
export async function locationAccessDenied(): Promise<boolean> {
  if (!canUseDeviceLocation()) return false;
  try {
    const Location = await import("expo-location");
    return (await Location.getForegroundPermissionsAsync()).status === "denied";
  } catch {
    console.warn("[location] permission could not be read");
    return false;
  }
}

/**
 * A fix this recent and this precise answers "near me" or "where am I" without
 * a new one. Accuracy is not distance moved: two minutes on foot is a few hundred
 * metres, so a fix taken faster than a brisk walk is not reused at all.
 */
const RECENT_FIX_MAX_AGE_MS = 2 * 60_000;
const RECENT_FIX_ACCURACY_M = 500;
const RECENT_FIX_MAX_SPEED_MPS = 2;
/** With no recent fix, how long a send waits for a new one before going without. */
const NEW_FIX_TIMEOUT_MS = 5_000;
/** The place name is a nicety: coordinates alone serve the server. */
const PLACE_NAME_TIMEOUT_MS = 1_500;
const NAME_PENDING = Symbol("place name pending");

/** `work`'s value, or `fallback` once `ms` pass first. */
function within<T, F>(work: Promise<T>, ms: number, fallback: F): Promise<T | F> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => resolve(fallback), ms);
    work.then(
      (value) => { clearTimeout(timer); resolve(value); },
      (error: unknown) => { clearTimeout(timer); reject(error); },
    );
  });
}

async function recentFix(Location: ExpoLocationModule) {
  try {
    const fix = await Location.getLastKnownPositionAsync({
      maxAge: RECENT_FIX_MAX_AGE_MS,
      requiredAccuracy: RECENT_FIX_ACCURACY_M,
    });
    // Speed is null, or negative on iOS, when the fix does not know it.
    return fix && (fix.coords.speed ?? 0) > RECENT_FIX_MAX_SPEED_MPS ? null : fix;
  } catch {
    return null;
  }
}

async function placeName(
  Location: ExpoLocationModule,
  latitude: number,
  longitude: number,
): Promise<string | null> {
  try {
    const place = (await Location.reverseGeocodeAsync({ latitude, longitude }))[0];
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

/** The phone's location services are off, or the read failed for want of them. */
const SERVICES_OFF = /SETTINGS_UNSATISFIED|LOCATION_IS_UNAVAILABLE|LOCATION_UNAVAILABLE/;

/**
 * A new fix at Balanced, a city or a neighbourhood. `ask`: the user asked for this read,
 * and Android may offer Play services' one-tap "turn on location" over the app; a read
 * nobody asked for (the sync on opening) never shows it (a Galaxy S23, 2026-11-10).
 * Null when location services are off: no fix, not a refusal, so a chat turn still goes.
 */
async function newFix(Location: ExpoLocationModule, ask: boolean) {
  try {
    return await Location.getCurrentPositionAsync({
      accuracy: Location.Accuracy.Balanced,
      mayShowUserSettingsDialog: ask,
    });
  } catch (error) {
    const code = (error as { code?: unknown } | null)?.code;
    if (typeof code === "string" && SERVICES_OFF.test(code)) return null;
    // A read that cannot tell either is the failure it was (`runWithLocationPermission`).
    if (!(await Location.hasServicesEnabledAsync())) return null;
    throw error;
  }
}

/**
 * A new fix, or for a `quick` read (a chat send) a recent one when there is
 * one, and null when none comes within `NEW_FIX_TIMEOUT_MS`. A quick read's
 * place name that is slower than `PLACE_NAME_TIMEOUT_MS` comes as `lateLabel`.
 */
async function readDeviceGeo(Location: ExpoLocationModule, quick: boolean, ask: boolean): Promise<DeviceGeo | null> {
  const pos = quick
    ? (await recentFix(Location)) ?? (await within(newFix(Location, ask), NEW_FIX_TIMEOUT_MS, null))
    : await newFix(Location, ask);
  if (!pos) return null;
  const { latitude, longitude } = pos.coords;
  const naming = placeName(Location, latitude, longitude);
  const label = quick ? await within(naming, PLACE_NAME_TIMEOUT_MS, NAME_PENDING) : await naming;
  if (label === NAME_PENDING) return { label: null, latitude, longitude, lateLabel: naming };
  return { label, latitude, longitude };
}

/**
 * Request location the way other apps do: show the system permission sheet
 * when possible. Only report `blocked` when the OS will not show that sheet again.
 * `quick` (a chat send) takes a recent fix and bounds the waits; Settings asks
 * for a new fix and waits for it.
 */
export async function requestDeviceGeo(
  options: { quick?: boolean; ask?: boolean } = {},
): Promise<DeviceGeoRequestResult> {
  const result = await runWithLocationPermission(
    (Location) => readDeviceGeo(Location, options.quick === true, options.ask !== false),
    options.ask !== false,
  );
  if (result.status !== "granted") return { status: result.status };
  return result.value ? { status: "granted", geo: result.value } : { status: "no_fix" };
}

/**
 * City/region label from device GPS + reverse geocode, or null if unavailable.
 * `ask: false` shows nothing: no permission sheet (`runWithLocationPermission`) and no
 * "turn on location" dialog (`newFix`).
 */
export async function getDeviceLocationLabel(options: { ask?: boolean } = {}): Promise<string | null> {
  const result = await requestDeviceGeo({ ask: options.ask });
  return result.status === "granted" ? result.geo.label : null;
}

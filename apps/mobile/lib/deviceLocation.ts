import { canUseDeviceLocation } from "@/lib/expoRuntime";

/** City/region label from device GPS + reverse geocode, or null if unavailable. */
export async function getDeviceLocationLabel(): Promise<string | null> {
  if (!canUseDeviceLocation()) {
    return null;
  }

  try {
    const Location = await import("expo-location");
    const perm = await Location.getForegroundPermissionsAsync();
    let granted = perm.status === "granted";
    if (!granted) {
      const req = await Location.requestForegroundPermissionsAsync();
      granted = req.status === "granted";
    }
    if (!granted) return null;

    const pos = await Location.getCurrentPositionAsync({
      accuracy: Location.Accuracy.Balanced,
    });
    const places = await Location.reverseGeocodeAsync({
      latitude: pos.coords.latitude,
      longitude: pos.coords.longitude,
    });
    const place = places[0];
    if (!place) return null;

    const parts = [place.city, place.region, place.country].filter(
      (p): p is string => Boolean(p?.trim()),
    );
    return parts.length > 0 ? parts.join(", ") : null;
  } catch {
    return null;
  }
}

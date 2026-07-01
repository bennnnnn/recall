import { canUseDeviceLocation } from "@/lib/expoRuntime";

export type DeviceGeo = {
  label: string | null;
  latitude: number;
  longitude: number;
};

/** GPS coordinates + optional city/region from reverse geocode. */
export async function getDeviceGeo(): Promise<DeviceGeo | null> {
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
  } catch {
    return null;
  }
}

/** City/region label from device GPS + reverse geocode, or null if unavailable. */
export async function getDeviceLocationLabel(): Promise<string | null> {
  const geo = await getDeviceGeo();
  return geo?.label ?? null;
}

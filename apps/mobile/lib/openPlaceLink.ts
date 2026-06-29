import { Linking } from "react-native";

import { googleMapsSearchUrl, isGenericSearchUrl } from "@/lib/placesList";

export async function openPlaceLink(url: string, label?: string): Promise<void> {
  const trimmed = url.trim();
  const fallback = label?.trim() ? googleMapsSearchUrl(label.trim()) : "";
  const target =
    trimmed && !isGenericSearchUrl(trimmed)
      ? trimmed
      : fallback || trimmed;

  if (!target) return;

  try {
    await Linking.openURL(target);
    return;
  } catch {
    if (fallback && fallback !== target) {
      try {
        await Linking.openURL(fallback);
      } catch {
        // ignore — simulator may lack Maps/browser handler
      }
    }
  }
}

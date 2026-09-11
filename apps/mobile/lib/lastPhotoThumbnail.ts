import { useCallback, useEffect, useState } from "react";
import { getPermissionsAsync } from "expo-media-library";
import { getAssetsAsync } from "expo-media-library/legacy";

/** Best-effort last Camera Roll photo. Never prompts — icon fallback if denied. */
export async function loadLastPhotoUri(): Promise<string | null> {
  try {
    const permission = await getPermissionsAsync();
    if (!permission.granted) return null;
    const page = await getAssetsAsync({
      first: 1,
      mediaType: ["photo"],
      sortBy: ["creationTime"],
    });
    return page.assets[0]?.uri ?? null;
  } catch {
    return null;
  }
}

/** Loads the Photos thumb only when the scanner is shown; never prompts. */
export function useLastPhotoThumb(visible: boolean): string | null {
  const [uri, setUri] = useState<string | null>(null);
  const load = useCallback(() => {
    void loadLastPhotoUri().then(setUri);
  }, []);
  useEffect(() => {
    if (visible) load();
  }, [visible, load]);
  return uri;
}

import * as SecureStore from "expo-secure-store";

import {
  normalizeAppearancePreference,
  type AppearancePreference,
} from "@/lib/appearance";

const KEY = "appearance_preference";

let cachedPreference: AppearancePreference | null = null;

export async function getAppearancePreference(): Promise<AppearancePreference> {
  if (cachedPreference !== null) return cachedPreference;
  try {
    const raw = await SecureStore.getItemAsync(KEY);
    cachedPreference = normalizeAppearancePreference(raw);
  } catch {
    cachedPreference = "system";
  }
  return cachedPreference;
}

export async function setAppearancePreference(
  preference: AppearancePreference,
): Promise<void> {
  cachedPreference = preference;
  try {
    await SecureStore.setItemAsync(KEY, preference);
  } catch {
    /* Keychain may be unavailable on unsigned simulator builds */
  }
}

/** Test helper — reset in-memory cache between cases. */
export function resetAppearancePreferenceCache(): void {
  cachedPreference = null;
}

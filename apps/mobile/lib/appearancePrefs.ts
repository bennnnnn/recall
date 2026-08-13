/**
 * Persist light/dark/system appearance. Not a secret — use the filesystem,
 * not SecureStore (Keychain). A linker-signed / entitlement-less simulator
 * build rejects Keychain writes with errSecMissingEntitlement (-34018), which
 * used to silently drop the user's preference on next launch.
 */

import {
  documentDirectory,
  getInfoAsync,
  readAsStringAsync,
  writeAsStringAsync,
} from "expo-file-system/legacy";
import * as SecureStore from "expo-secure-store";

import {
  normalizeAppearancePreference,
  type AppearancePreference,
} from "@/lib/appearance";

const LEGACY_KEY = "appearance_preference";
const FILE_NAME = "recall.appearance-preference.txt";

let cachedPreference: AppearancePreference | null = null;

function filePath(): string | null {
  if (!documentDirectory) return null;
  return `${documentDirectory}${FILE_NAME}`;
}

async function loadLegacySecureStore(): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(LEGACY_KEY);
  } catch {
    return null;
  }
}

export async function getAppearancePreference(): Promise<AppearancePreference> {
  if (cachedPreference !== null) return cachedPreference;
  const path = filePath();
  if (path) {
    try {
      const info = await getInfoAsync(path);
      if (info.exists) {
        cachedPreference = normalizeAppearancePreference(await readAsStringAsync(path));
        return cachedPreference;
      }
    } catch {
      /* fall through to legacy */
    }
  }

  const legacy = await loadLegacySecureStore();
  cachedPreference = normalizeAppearancePreference(legacy);
  if (legacy === "light" || legacy === "dark") {
    await setAppearancePreference(cachedPreference);
  }
  return cachedPreference;
}

export async function setAppearancePreference(
  preference: AppearancePreference,
): Promise<void> {
  cachedPreference = preference;
  const path = filePath();
  if (!path) return;
  try {
    await writeAsStringAsync(path, preference);
  } catch {
    /* best-effort — in-memory preference still applies this session */
  }
}

/** Test helper — reset in-memory cache between cases. */
export function resetAppearancePreferenceCache(): void {
  cachedPreference = null;
}

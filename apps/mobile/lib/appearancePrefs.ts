/**
 * Persist light/dark/system appearance. Not a secret — use the filesystem,
 * not SecureStore (Keychain). A linker-signed / entitlement-less simulator
 * build rejects Keychain writes with errSecMissingEntitlement (-34018), which
 * used to silently drop the user's preference on next launch.
 */

import {
  normalizeAppearancePreference,
  type AppearancePreference,
} from "@/lib/appearance";
import { prefFilePath, readLegacySecureStore, readPrefFile, writePrefFile } from "@/lib/filePrefs";

const LEGACY_KEY = "appearance_preference";
const FILE_NAME = "recall.appearance-preference.txt";

let cachedPreference: AppearancePreference | null = null;

function filePath(): string | null {
  return prefFilePath(FILE_NAME);
}

export async function getAppearancePreference(): Promise<AppearancePreference> {
  if (cachedPreference !== null) return cachedPreference;
  const fromFile = await readPrefFile(filePath());
  if (fromFile !== null) {
    cachedPreference = normalizeAppearancePreference(fromFile);
    return cachedPreference;
  }

  const legacy = await readLegacySecureStore(LEGACY_KEY);
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
  await writePrefFile(filePath(), preference);
}

/** Test helper — reset in-memory cache between cases. */
export function resetAppearancePreferenceCache(): void {
  cachedPreference = null;
}

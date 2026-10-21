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
import {
  prefFilePath,
  readLegacySecureStore,
  readPrefFile,
  readPrefFileSync,
  writePrefFile,
} from "@/lib/filePrefs";

const LEGACY_KEY = "appearance_preference";
const FILE_NAME = "recall.appearance-preference.txt";

let cachedPreference: AppearancePreference | null = null;

function filePath(): string | null {
  return prefFilePath(FILE_NAME);
}

/** The saved preference, read before the first render; null when there is no file yet. */
export function readAppearancePreferenceSync(): AppearancePreference | null {
  if (cachedPreference !== null) return cachedPreference;
  const fromFile = readPrefFileSync(FILE_NAME);
  if (fromFile === null) return null;
  cachedPreference = normalizeAppearancePreference(fromFile);
  return cachedPreference;
}

export async function getAppearancePreference(): Promise<AppearancePreference> {
  if (cachedPreference !== null) return cachedPreference;
  const fromFile = await readPrefFile(filePath());
  if (fromFile !== null) {
    cachedPreference = normalizeAppearancePreference(fromFile);
    return cachedPreference;
  }

  // A one-time move out of the Keychain. The file is written whatever it held,
  // "system" included, so later launches read the file and never the Keychain.
  const legacy = normalizeAppearancePreference(await readLegacySecureStore(LEGACY_KEY));
  // A choice made in Settings meanwhile wins over the old value.
  if (cachedPreference !== null) return cachedPreference;
  await setAppearancePreference(legacy);
  return legacy;
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

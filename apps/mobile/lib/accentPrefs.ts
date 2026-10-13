/**
 * Persist the accent color. Not a secret — a file, like the appearance
 * preference, so a simulator build without Keychain entitlements keeps it.
 */

import { normalizeAccentPreference, type AccentPreference } from "@/lib/accent";
import { prefFilePath, readPrefFile, writePrefFile } from "@/lib/filePrefs";

const FILE_NAME = "recall.accent-preference.txt";

let cachedAccent: AccentPreference | null = null;

export async function getAccentPreference(): Promise<AccentPreference> {
  if (cachedAccent !== null) return cachedAccent;
  cachedAccent = normalizeAccentPreference(await readPrefFile(prefFilePath(FILE_NAME)));
  return cachedAccent;
}

export async function setAccentPreference(accent: AccentPreference): Promise<void> {
  cachedAccent = accent;
  await writePrefFile(prefFilePath(FILE_NAME), accent);
}

/** Test helper — reset in-memory cache between cases. */
export function resetAccentPreferenceCache(): void {
  cachedAccent = null;
}

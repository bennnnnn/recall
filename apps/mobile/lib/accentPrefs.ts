/**
 * Persist the accent color. Not a secret — a file, like the appearance
 * preference, so a simulator build without Keychain entitlements keeps it.
 */

import { DEFAULT_ACCENT, normalizeAccentPreference, type AccentPreference } from "@/lib/accent";
import { createFilePref } from "@/lib/filePrefs";

const accentPref = createFilePref<AccentPreference>("recall.accent-preference.txt", normalizeAccentPreference);

/** The saved accent, read before the first render; the default with no file yet. */
export function readAccentPreferenceSync(): AccentPreference {
  return accentPref.readSync() ?? DEFAULT_ACCENT;
}

export const { get: getAccentPreference, set: setAccentPreference, reset: resetAccentPreferenceForTest } = accentPref;

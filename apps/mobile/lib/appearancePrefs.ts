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
import { createFilePref } from "@/lib/filePrefs";

const appearancePref = createFilePref<AppearancePreference>(
  "recall.appearance-preference.txt",
  normalizeAppearancePreference,
);

export const {
  /** The saved preference, read before the first render; null when there is no file yet. */
  readSync: readAppearancePreferenceSync,
  get: getAppearancePreference,
  set: setAppearancePreference,
  reset: resetAppearancePreferenceCache,
} = appearancePref;

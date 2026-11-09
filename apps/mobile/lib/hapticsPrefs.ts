/**
 * Persist Settings → Haptics. Not a secret — a file, like the appearance
 * preference, so a simulator build without Keychain entitlements keeps it.
 */

import { createFilePref } from "@/lib/filePrefs";

const hapticsPref = createFilePref(
  "recall.haptics.txt",
  (raw) => raw?.trim() !== "off",
  (enabled) => (enabled ? "on" : "off"),
);

export const { get: getHapticsPreference, set: setHapticsPreference } = hapticsPref;

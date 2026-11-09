/** Onboarding is a non-secret device preference; auth credentials stay in SecureStore. */
import { createFilePref } from "@/lib/filePrefs";

const onboardedPref = createFilePref(
  "recall.onboarded.txt",
  (raw) => raw === "1",
  (onboarded) => (onboarded ? "1" : "0"),
);

export const getOnboarded = onboardedPref.get;

export function setOnboarded(): Promise<void> {
  return onboardedPref.set(true);
}

export function clearOnboarded(): Promise<void> {
  return onboardedPref.set(false);
}

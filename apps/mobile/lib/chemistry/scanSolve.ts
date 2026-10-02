import { CHEMISTRY_CAMERA_PROMPT } from "@/lib/scanner/subjects";

/** Protocol line after the chemistry camera caption. Must stay byte-for-byte
 * identical to CHEMISTRY_CAMERA_CONFIRMED_PREFIX on the API. */
export const CHEMISTRY_CAMERA_CONFIRMED_PREFIX = "I read this as:";

/** Confirmed chemistry text is sent alone, with no photo and no steps prefix. */
export function chemistryScanSolveMessage(reading: string): string {
  return reading.trim();
}

/** Caption after the student confirms the chemistry reading. An empty
 * reading falls back to the camera prompt so send still marks chemistry. */
export function composerTextAfterChemistryScanConfirm(reading: string): string {
  const trimmed = reading.trim();
  if (!trimmed) return CHEMISTRY_CAMERA_PROMPT;
  return `${CHEMISTRY_CAMERA_PROMPT}\n\n${CHEMISTRY_CAMERA_CONFIRMED_PREFIX} ${trimmed}`;
}

/** Preset caption for the camera math solver entry point. Must stay
 * byte-for-byte identical to MATH_CAMERA_PROMPT in
 * apps/api/app/services/math_image_extract.py — the backend matches this
 * exact string to trigger verified-math augmentation for the camera flow.
 *
 * Kept in its own dependency-free module (not lib/attachments.ts) so
 * consumers that only need the string — like messageAttachments.ts, which
 * Jest tests without Expo native-module mocks — don't pull in
 * expo-document-picker/expo-image-picker/expo-file-system transitively. */
export const MATH_CAMERA_PROMPT = "Solve the math problem in this image step by step.";

/** Protocol line the scanner sends after the user confirms OCR. Must stay
 * byte-for-byte identical to MATH_CAMERA_CONFIRMED_PREFIX on the API. */
export const MATH_CAMERA_CONFIRMED_PREFIX = "I read this as:";

export function isMathCameraPrompt(text: string): boolean {
  const folded = text.trim().toLowerCase();
  const prompt = MATH_CAMERA_PROMPT.toLowerCase();
  return folded === prompt || folded.startsWith(`${prompt}\n`);
}

export function composerTextAfterMathScan(existing: string, scanPrompt: string = MATH_CAMERA_PROMPT): string {
  return existing.trim() ? existing : scanPrompt;
}

/** Caption after the student confirms (or edits) the OCR reading. Empty
 * reading falls back to the camera prompt so send still triggers math. */
export function composerTextAfterMathScanConfirm(reading: string): string {
  const trimmed = reading.trim();
  if (!trimmed) return MATH_CAMERA_PROMPT;
  return `${MATH_CAMERA_PROMPT}\n\n${MATH_CAMERA_CONFIRMED_PREFIX} ${trimmed}`;
}

/** The steps ask a confirmed scan is sent with; the API lessons read it. */
export const MATH_SCAN_SOLVE_PREFIX = "Show steps:";

const RELATION = /[=<>\u2264\u2265]/;

/**
 * The message a confirmed scan sends as ordinary text, so the whole text
 * pipeline (lessons, systems, word problems) sees it. Relations on separate
 * lines join with commas ("x+y=5, x-y=1") so a system reads as one problem;
 * any other lines join with spaces.
 */
export function mathScanSolveMessage(reading: string): string {
  const lines = reading
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length === 0) return "";
  const joined = lines.every((line) => RELATION.test(line)) ? lines.join(", ") : lines.join(" ");
  return `${MATH_SCAN_SOLVE_PREFIX} ${joined}`;
}

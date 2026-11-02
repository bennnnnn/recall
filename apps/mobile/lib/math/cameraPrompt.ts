/** Preset caption for the camera math solver entry point. The API recognizes this
 * exact string (apps/api/app/services/subject_scan.py); both sides compare it with
 * docs/fixtures/scanner_prompts.json.
 *
 * Kept in its own dependency-free module so consumers that only need the string —
 * like messageAttachments.ts, which Jest tests without Expo native-module mocks —
 * don't pull in expo-document-picker/expo-image-picker/expo-file-system transitively. */
export const MATH_CAMERA_PROMPT = "Solve the math problem in this image step by step.";

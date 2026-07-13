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

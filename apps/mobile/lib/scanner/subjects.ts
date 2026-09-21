import { MATH_CAMERA_PROMPT } from "@/lib/math/cameraPrompt";

export const SCANNER_SUBJECTS = ["math", "physics", "chemistry"] as const;

export type ScannerSubject = (typeof SCANNER_SUBJECTS)[number];

export const PHYSICS_CAMERA_PROMPT =
  "Solve the physics problem in this image step by step.";
export const CHEMISTRY_CAMERA_PROMPT =
  "Solve the chemistry problem in this image step by step.";

export const SCANNER_CAMERA_PROMPTS: Record<ScannerSubject, string> = {
  math: MATH_CAMERA_PROMPT,
  physics: PHYSICS_CAMERA_PROMPT,
  chemistry: CHEMISTRY_CAMERA_PROMPT,
};

export function scannerCameraPrompt(subject: ScannerSubject): string {
  return SCANNER_CAMERA_PROMPTS[subject];
}

export function isScannerCameraPrompt(text: string): boolean {
  const folded = text.trim().toLowerCase();
  return Object.values(SCANNER_CAMERA_PROMPTS).some((prompt) => {
    const expected = prompt.toLowerCase();
    return folded === expected || folded.startsWith(`${expected}\n`);
  });
}

export function composerTextAfterSubjectScan(
  existing: string,
  subject: ScannerSubject,
): string {
  const prompt = scannerCameraPrompt(subject);
  return existing.trim() ? `${prompt}\n\n${existing}` : prompt;
}

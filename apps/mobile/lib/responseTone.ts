export const RESPONSE_TONES = ["funny", "professional", "casual", "soft"] as const;

export type ResponseTone = (typeof RESPONSE_TONES)[number];

export const DEFAULT_RESPONSE_TONE: ResponseTone = "funny";

export function normalizeResponseTone(value: string | null | undefined): ResponseTone {
  if (value && (RESPONSE_TONES as readonly string[]).includes(value)) {
    return value as ResponseTone;
  }
  return DEFAULT_RESPONSE_TONE;
}

type ExifRecord = Record<string, unknown>;

const BRIGHTNESS_THRESHOLD = 1.25;
const SLOW_EXPOSURE_SECONDS = 1 / 24;
const HIGH_ISO = 400;

/**
 * Derive a low-light signal from the camera's real exposure metadata.
 * Returns null when a device does not publish enough EXIF data.
 */
export function isLowLightExif(exif: unknown): boolean | null {
  if (!isRecord(exif)) return null;

  const brightness = findNumber(exif, ["brightnessvalue", "brightness"]);
  if (brightness !== null) return brightness <= BRIGHTNESS_THRESHOLD;

  const exposure = findNumber(exif, ["exposuretime"]);
  const iso = findNumber(exif, ["photographicsensitivity", "isospeedratings", "iso"]);
  if (exposure === null || iso === null) return null;
  if (exposure >= SLOW_EXPOSURE_SECONDS && iso >= HIGH_ISO) return true;
  if (exposure < SLOW_EXPOSURE_SECONDS || iso < HIGH_ISO) return false;
  return null;
}

function findNumber(record: ExifRecord, keys: readonly string[]): number | null {
  for (const [rawKey, value] of Object.entries(record)) {
    const key = rawKey.toLowerCase().replace(/[^a-z]/g, "");
    if (keys.includes(key)) {
      const parsed = numericValue(value);
      if (parsed !== null) return parsed;
    }
  }
  for (const value of Object.values(record)) {
    if (!isRecord(value)) continue;
    const nested = findNumber(value, keys);
    if (nested !== null) return nested;
  }
  return null;
}

function numericValue(value: unknown): number | null {
  if (Array.isArray(value)) return numericValue(value[0]);
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value !== "string") return null;
  const fraction = value.trim().match(/^(-?\d+(?:\.\d+)?)\s*\/\s*(\d+(?:\.\d+)?)$/);
  if (fraction) {
    const denominator = Number(fraction[2]);
    return denominator === 0 ? null : Number(fraction[1]) / denominator;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function isRecord(value: unknown): value is ExifRecord {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

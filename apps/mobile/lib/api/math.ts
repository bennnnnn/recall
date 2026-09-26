import { readAsStringAsync } from "expo-file-system/legacy";

import { request } from "@/lib/api/client";
import { getSessionGeneration, requireTokenSession, SessionChangedError } from "@/lib/auth";

/** What the scanner read, for the student to confirm or edit before solving. */
export type MathScanReading = {
  /** Plain editable math ("2x + 3 = 7"); empty when nothing was legible. */
  reading: string;
  /** Hard to read: the review asks the student to check it closely. */
  uncertain: boolean;
  source: "mathpix" | "vision" | "none";
};

const SCAN_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

/**
 * OCR a cropped scan without solving it. The file is base64-encoded natively
 * (a JS-thread encode of a full photo froze the scanner once before).
 */
export async function readMathScan(
  token: string,
  scan: { localUri: string; contentType: string },
  signal?: AbortSignal,
): Promise<MathScanReading> {
  requireTokenSession(token);
  const generation = getSessionGeneration();
  const imageBase64 = await readAsStringAsync(scan.localUri, { encoding: "base64" });
  if (generation !== getSessionGeneration()) throw new SessionChangedError();
  return request<MathScanReading>(
    "/math/scan/read",
    token,
    {
      method: "POST",
      body: JSON.stringify({
        image_base64: imageBase64,
        content_type: SCAN_TYPES.has(scan.contentType) ? scan.contentType : "image/jpeg",
      }),
      signal,
    },
    true,
    25_000,
  );
}

export const mathApi = {
  readMathScan,
};

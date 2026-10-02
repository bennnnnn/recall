import { readAsStringAsync } from "expo-file-system/legacy";

import { request } from "@/lib/api/client";
import { getSessionGeneration, requireTokenSession, SessionChangedError } from "@/lib/auth";

/** The written chemistry problem, for the student to confirm before solving. */
export type ChemistryScanReading = {
  reading: string;
  uncertain: boolean;
  source: "vision" | "none";
};

const SCAN_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

/** Read a chemistry crop as plain text. It does not solve the problem. */
export async function readChemistryScan(
  token: string,
  scan: { localUri: string; contentType: string },
  signal?: AbortSignal,
): Promise<ChemistryScanReading> {
  requireTokenSession(token);
  const generation = getSessionGeneration();
  const imageBase64 = await readAsStringAsync(scan.localUri, { encoding: "base64" });
  if (generation !== getSessionGeneration()) throw new SessionChangedError();
  return request<ChemistryScanReading>(
    "/chemistry/scan/read",
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

export const chemistryApi = {
  readChemistryScan,
};
